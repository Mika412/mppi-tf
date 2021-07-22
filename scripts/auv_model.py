import tensorflow as tf
import numpy as np
from model_base import ModelBase

gpu = tf.config.list_physical_devices('GPU')
tf.config.experimental.set_memory_growth(device=gpu[0], enable=True)


def skew_op(vec):     
    S = np.zeros(shape=(3, 3))
    
    S[0, 1] = -vec[2]
    S[0, 2] =  vec[1]
    
    S[1, 0] =  vec[2]
    S[1, 2] = -vec[0]

    S[2, 0] = -vec[1]
    S[2, 1] =  vec[0]
    return tf.constant(S, dtype=tf.float64)

def tf_skew_op(scope, vec):
    with tf.name_scope(scope) as scope:
        vec = tf.expand_dims(vec, axis=-1)
        O_pad = tf.zeros(shape=(1), dtype=tf.float64)
        r0 = tf.expand_dims(tf.concat([O_pad, -vec[2], vec[1]], axis=-1), axis=1)
        r1 = tf.expand_dims(tf.concat([vec[2], O_pad,  -vec[0]], axis=-1), axis=1)
        r2 = tf.expand_dims(tf.concat([-vec[1], vec[0], O_pad], axis=-1), axis=1)

        S = tf.concat([r0, r1, r2], axis=1)
        return S

def skew_op_k(batch):
    k = batch.shape[0]
    S = np.zeros(shape=(k, 3, 3))
    
    S[:, 0, 1] = -batch[:, 2]
    S[:, 0, 2] =  batch[:, 1]
    
    S[:, 1, 0] =  batch[:, 2]
    S[:, 1, 2] = -batch[:, 0]

    S[:, 2, 0] = -batch[:, 1]
    S[:, 2, 1] =  batch[:, 0]
    return S

def tf_skew_op_k(scope, batch):
    with tf.name_scope(scope) as scope:
        k = batch.shape[0]
        vec = tf.expand_dims(batch, axis=-1)
    
        O_pad = tf.zeros(shape=(k, 1), dtype=tf.float64)
        r0 = tf.expand_dims(tf.concat([O_pad, -vec[:, 2], vec[:, 1]], axis=-1), axis=1)
        r1 = tf.expand_dims(tf.concat([vec[:, 2], O_pad,  -vec[:, 0]], axis=-1), axis=1)
        r2 = tf.expand_dims(tf.concat([-vec[:, 1], vec[:, 0], O_pad], axis=-1), axis=1)
    
        S = tf.concat([r0, r1, r2], axis=1)
        return S

'''
    AUV dynamical model based on the UUV_sim vehicle model
    and implemented in tensorflow to be used with the MPPI
    controller.
'''
class AUVModel(ModelBase):
    def __init__(self, inertial_frame_id='world', quat=False, action_dim=6, name="AUV", k=1, dt=0.1, parameters=dict()):
        '''
            Class constructor
        '''
        self.dt = dt
        if quat:
            self._quat=True
            state_dim=13
        else:
            self._quat=False
            state_dim=12

        ModelBase.__init__(self, state_dim, action_dim, name, k)

        assert  inertial_frame_id in ['world', 'world_ned']

        self.inertial_frame_id = inertial_frame_id
        if self.inertial_frame_id == 'world':
            self.body_frame_id = 'base_link'
        else:
            self.body_frame_id = 'base_link_ned'

        self.mass = 0
        if "mass" in parameters:
            self.mass = tf.Variable(parameters['mass'], trainable=True, dtype=tf.float64)
        assert (self.mass > 0), "Mass has to be positive."
        
        self.volume = 0
        if "volume" in parameters:
            self.volume = parameters["volume"]
        assert (self.volume > 0), "Volume has to be positive."

        self.density = 0
        if "density" in parameters:
            self.density = parameters["density"]
        assert (self.density > 0), "Liquid density has to be positive."

        self.height = 0
        if "height" in parameters:
            self.height = parameters["height"]
        assert (self.height > 0), "Height has to be positive."

        self.length = 0
        if "length" in parameters:
            self.length = parameters["length"]
        assert (self.length > 0), "Length has to be positive."

        self.width = 0
        if "width" in parameters:
            self.width = parameters["width"]
        assert (self.width > 0), "Width has to be positive."

        if "cog" in parameters:
            self.cog = tf.constant(parameters["cog"], dtype=tf.float64)
            assert (len(self.cog) == 3), 'Invalid center of gravity vector. Size != 3'
        else:
            raise AssertionError("need to define the center of gravity in the body frame")

        if "cob" in parameters:
            self.cob = tf.constant(parameters["cob"], dtype=tf.float64)
            assert (len(self.cob) == 3), "Invalid center of buoyancy vector. Size != 3"
        else:
            raise AssertionError("need to define the center of buoyancy in the body frame")

        added_mass = np.zeros((6, 6))
        if "Ma" in parameters:
            added_mass = np.array(parameters["Ma"])
            assert (added_mass.shape == (6, 6)), "Invalid add mass matrix"
        self.added_mass = tf.constant(added_mass, dtype=tf.float64)
        
        damping = np.zeros(shape=(6, 6))
        if "linear_damping" in parameters:
            damping = np.array(parameters["linear_damping"])
            if damping.shape == (6,):
                damping = np.diag(damping)
            assert (damping.shape == (6, 6)), "Linear damping must be given as a 6x6 matrix or the diagonal coefficients"
        self.linear_damping = tf.constant(damping, dtype=tf.float64)

        quad_damping = np.zeros(shape=(6,))
        if "quad_damping" in parameters:
            quad_damping = np.array(parameters["quad_damping"])
            assert (quad_damping.shape == (6,)), "Quadratic damping must be given defined with 6 coefficients"
        self.quad_damping = tf.linalg.diag(quad_damping)

        damping_forward = np.zeros(shape=(6, 6))
        if "linear_damping_forward_speed" in parameters:
            damping_forward = np.array(parameters["linear_damping_forward_speed"])
            if damping_forward.shape == (6,):
                damping_forward = np.diag(damping_forward)
            assert (damping_forward.shape == (6, 6)), "Linear damping proportional to the \
                                                      forward speed must be given as a 6x6 \
                                                      matrix or the diagonal coefficients"
        self.linear_damping_forward_speed = tf.expand_dims(tf.constant(damping_forward, dtype=tf.float64), axis=0)

        inertial = dict(ixx=0, iyy=0, izz=0, ixy=0, ixz=0, iyz=0)
        if "inertial" in parameters:
            inertial_arg = parameters["inertial"]
            for key in inertial:
                if key not in inertial_arg:
                    raise AssertionError('Invalid moments of inertia')

        self.inertial = self.getInertial(inertial_arg)

        self.unit_z = tf.constant([0., 0., 1.], dtype=tf.float64)        

        self.gravity = 9.81

        self.mass_eye = self.mass * tf.eye(3, dtype=tf.float64)
        self.mass_lower =  self.mass * tf_skew_op("Skew_cog", self.cog)
        self.rb_mass = self.rigid_body_mass()
        self._Mtot = self.total_mass()

    def rigid_body_mass(self):
        upper = tf.concat([self.mass_eye, -self.mass_lower], axis=1)
        lower = tf.concat([self.mass_lower, self.inertial], axis=1)
        return tf.concat([upper, lower], axis=0)

    def total_mass(self):
        return tf.add(self.rb_mass, self.added_mass)

    def getInertial(self, dict):
        # buid the inertial matrix
        ixx = tf.Variable(dict['ixx'], trainable=True, dtype=tf.float64)
        ixy = tf.Variable(dict['ixy'], trainable=True, dtype=tf.float64)
        ixz = tf.Variable(dict['ixz'], trainable=True, dtype=tf.float64)
        iyy = tf.Variable(dict['iyy'], trainable=True, dtype=tf.float64)
        iyz = tf.Variable(dict['iyz'], trainable=True, dtype=tf.float64)
        izz = tf.Variable(dict['izz'], trainable=True, dtype=tf.float64)
        
        row0 = tf.expand_dims(tf.concat([ixx, ixy, ixz], axis=0), axis=0)
        row1 = tf.expand_dims(tf.concat([ixy, iyy, iyz], axis=0), axis=0)
        row2 = tf.expand_dims(tf.concat([ixz, iyz, izz], axis=0), axis=0)
        
        inertial = tf.concat([row0, row1, row2], axis=0)

        return inertial

    def buildStepGraph(self, scope, state, action):
        if self._quat:
            return self.step_q(scope, state, action)
        return self.step(scope, state, action)

    def step(self, scope, state, action):
        with tf.name_scope(scope) as scope:
            pose, speed = self.prepare_data(state)
            self.body2inertial_transform(pose)

            pose_dot = tf.matmul(self.get_jacobian(), speed)
            speed_dot = self.acc("acceleration", speed, action)

            pose_next = tf.add(self.dt*pose_dot, pose)
            speed_next = tf.add(self.dt*speed_dot, speed)
            return self.get_state(pose_next, speed_next)

    def step_q(self, scope, state, action):
        with tf.name_scope(scope) as scope:
            pose, speed = self.prepare_data(state)
            self.body2inertial_transform_q(pose)

            pose_dot = tf.matmul(self.get_jacobian_q(), speed)

            speed_dot = self.acc("acceleration", speed, action)

            pose_next = tf.add(self.dt*pose_dot, pose)
            speed_next = tf.add(self.dt*speed_dot, speed)
            return self.get_state(pose_next, speed_next)

    def get_jacobian(self):
        '''
        Returns J(\nu) \in $\mathbb{R}^{6 \cross 6}$ 
                     ---------------------------------------
            J(\nu) = | Rot_{n}^{b}(\Theta) 0^{3 \cross 3}  |
                     | 0^{3 \cross 3} T_{\theta}(\theta)   |
                     ---------------------------------------
        '''
        k = self._rotBtoI.shape[0]
        O_pad = tf.zeros(shape=(k, 3, 3), dtype=tf.float64)
        jac_r1 = tf.concat([self._rotBtoI, O_pad], axis=-1)
        jac_r2 = tf.concat([O_pad, self._TBtoIeuler], axis=-1)
        jac = tf.concat([jac_r1, jac_r2], axis=1)
        return jac

    def get_jacobian_q(self):
        '''
        Returns J(\nu) \in $\mathbb{R}^{7 \cross 7}$
                     ---------------------------------------
            J(\nu) = | q_{n}^{b}(\Theta) 0^{3 \cross 3}    |
                     | 0^{3 \cross 3} T_{\theta}(\theta)   |
                     ---------------------------------------
        '''
        k = self._rotBtoI.shape[0]
        print(k)
        O_pad3x3 = tf.zeros(shape=(k, 3, 3), dtype=tf.float64)
        print(O_pad3x3)
        O_pad4x3 = tf.zeros(shape=(k, 4, 3), dtype=tf.float64)
        print(O_pad4x3)
        print(self._TBtoIquat)
        jac_r1 = tf.concat([self._rotBtoI, O_pad3x3], axis=-1)
        print(jac_r1)
        jac_r2 = tf.concat([O_pad4x3, self._TBtoIquat], axis=-1)
        print(jac_r2)
        jac = tf.concat([jac_r1, jac_r2], axis=1)
        print(jac)
        return jac

    def body2inertial_transform(self, pose):
        '''
            Computes the rotational transform from body to inertial Rot_{n}^{b}(\Theta)
            and the attitude transformation T_{\theta}(\theta).

            input:
            ------
                - pose the robot pose expressed in inertial frame. Shape [k, 6, 1]

        '''
        k = pose.shape[0]
        angles = tf.squeeze(pose[:, 3:6, :], axis=-1)

        c = tf.expand_dims(tf.math.cos(angles), axis=-1)
        s = tf.expand_dims(tf.math.sin(angles), axis=-1)

        # cos(roll)/sin(roll)
        cr = c[:, 0]
        sr = s[:, 0]
        
        # cos(pitch)/sin(pitch)
        cp = c[:, 1]
        sp = s[:, 1]

        # cos(yaw)/sin(yaw)
        cy = c[:, 2]
        sy = s[:, 2]

        # build rotation matrix.
        O_pad = tf.zeros(shape=(k, 1), dtype=tf.float64)
        I_pad = tf.ones(shape=(k, 1), dtype=tf.float64)

        rz_r1 = tf.expand_dims(tf.concat([cy, -sy, O_pad], axis=-1), axis=1)
        rz_r2 = tf.expand_dims(tf.concat([sy, cy, O_pad], axis=-1), axis=1)
        rz_r3 = tf.expand_dims(tf.concat([O_pad, O_pad, I_pad], axis=-1), axis=1)

        Rz = tf.concat([rz_r1, rz_r2, rz_r3], axis=1)

        ry_r1 = tf.expand_dims(tf.concat([cp, O_pad, sp], axis=-1), axis=1)
        ry_r2 = tf.expand_dims(tf.concat([O_pad, I_pad, O_pad], axis=-1), axis=1)
        ry_r3 = tf.expand_dims(tf.concat([-sp, O_pad, cp], axis=-1), axis=1)

        Ry = tf.concat([ry_r1, ry_r2, ry_r3], axis=1)


        rx_r1 = tf.expand_dims(tf.concat([cr, -sr, O_pad], axis=-1), axis=1)
        rx_r2 = tf.expand_dims(tf.concat([sr, cr, O_pad], axis=-1), axis=1)
        rx_r3 = tf.expand_dims(tf.concat([O_pad, O_pad, I_pad], axis=-1), axis=1)

        Rx = tf.concat([rx_r1, rx_r2, rx_r3], axis=1)

        self._rotBtoI = tf.linalg.matmul(tf.matmul(Rz, Ry), Rx)

        TBtoI_r1 = tf.expand_dims(tf.concat([I_pad, tf.divide(tf.multiply(sr, sp), cp), tf.divide(tf.multiply(cr, sp), cp)], axis=-1), axis=1)
        TBtoI_r2 = tf.expand_dims(tf.concat([O_pad, cr, -sr], axis=-1), axis=1)
        TBtoI_r3 = tf.expand_dims(tf.concat([O_pad, tf.divide(sr, cp), tf.divide(cr, cp)], axis=-1), axis=1)

        self._TBtoIeuler = tf.concat([TBtoI_r1, TBtoI_r2, TBtoI_r3], axis=1)

    def body2inertial_transform_q(self, pose):
        '''
            Computes the rotational transform from body to inertial Rot_{n}^{b}(q)
            and the attitude transformation T_{q}(q).


            input:
            ------
                - pose the robot pose expressed in inertial frame. Shape [k, 6, 1]

        '''
        k = pose.shape[0]
        quat = tf.squeeze(pose[:, 3:7, :], axis=-1)

        w = quat[:, 0]
        x = quat[:, 1]
        y = quat[:, 2]
        z = quat[:, 3]

        r1 = tf.expand_dims(tf.concat([1 - 2 * (tf.pow(y, 2) + tf.pow(z, 2)),
                                        2 * (x * y - z * w),
                                        2 * (x * z + y * w)], axis=-1), axis=0)

        r2 = tf.expand_dims(tf.concat([2 * (x * y + z * w),
                                        1 - 2 * (tf.pow(x, 2) + tf.pow(z, 2)),
                                        2 * (y * z - x * w)], axis=-1), axis=0)

        r3 = tf.expand_dims(tf.concat([2 * (x * z - y * w),
                                        2 * (y * z + x * w),
                                        1 - 2 * (tf.pow(x, 2) + tf.pow(z, 2))], axis=-1), axis=0)

        self._rotBtoI = tf.concat([r1, r2, r3], axis=0)

        r1_t = tf.expand_dims(tf.concat([-x, -y, -z], axis=-1), axis=0)

        r2_t = tf.expand_dims(tf.concat([w, -z, -y], axis=-1), axis=0)

        r3_t = tf.expand_dims(tf.concat([z, w, -x], axis=-1), axis=0)

        r4_t = tf.expand_dims(tf.concat([-y, x, w], axis=-1), axis=0)

        self._TBtoIquat = 0.5 * tf.concat([r1_t, r2_t, r3_t, r4_t], axis=0)

        self._rotBtoI = tf.expand_dims(self._rotBtoI, axis=0)
        self._TBtoIquat = tf.expand_dims(self._TBtoIquat, axis=0)

    def prepare_data(self, state):
        if self._quat:
            pose = state[:, 0:7]
            speed = state[:, 7:13]
        else:
            pose = state[:, 0:6]
            speed = state[:, 6:12]
        return pose, speed

    def get_state(self, pose_next, speed_next):
        '''
            Return the state of the system after propagating it for one timestep.

            input:
            ------
                - pose_next: float64 tensor. Shape [k/1, 6/7, 1]. 6 If euler representation, 7 if quaternion.
                - speed_next: float64 tensor. Shape [k, 6, 1]

            output:
            -------
                - next_state: float64 tensor. Shape [k, 12/13, 1]
        '''
        if self._quat:
            pose_next = self.normalize_quat(pose_next)
        k_p = pose_next.shape[0]
        k_s = speed_next.shape[0]
        # On the first step, the pose is only of size k=1.
        if k_p < k_s:
            pose_next = tf.broadcast_to(pose_next, [k_s, 6, 1])
        state = tf.concat([pose_next, speed_next], axis=1)
        return state

    def normalize_quat(self, pose):
        '''
            Normalizes the quaternions.

            input:
            ------

        '''
        pos = pose[:, 0:3]
        quat = pose[:, 3:7]
        quat = tf.divide(quat, tf.linalg.norm(quat))
        pose = tf.concat([pos, quat], axis=1)
        return pose

    def to_SNAME(self, x):
        '''
            Changes the representation of x to match the SNAME convention.

            input:
            ------
                - x. Float tensor, shape [k, 3/6, 1]

            output:
            -------
                - the tensor in the SNAME convention.

        '''

        if self._body_frame_id == 'base_link_ned':
            return x
        try:
            if x.shape[1] == 3:
                return tf.concat([x[:, 0, :], -1*x[:, 1, :], -1*x[:, 2, :]], axis=1)
            elif x.shape[1] == 6:
                return tf.concat([x[:, 0, :], -1*x[:, 1, :], -1*x[:, 2, :],
                                 x[:, 3, :], -1*x[:, 4, :], -1*x[:, 5, :]], axis=1)

        except Exception as e:
            print('Invalid input vector, v=' + str(x))
            print('Message=' + str(e))
            return None

    def from_SNAME(self, x):
        if self._body_frame_id == 'base_link_ned':
            return x
        return self.to_SNAME(x)

    def restoring_forces(self, scope, q=None, use_sname=False):
        '''
            computes the restoring forces. 

            input:
            ------
                - mass, float, the mass of the vehicle. in kg.
                - gravity, float, the gravity constant. in $\frac{N}{t^{2}}$
                - volume, float, the volume of the of the vehicle. In m^{3}.
                - density, float, the liquid density. In $\frac{kg}{m^{3}}$
                - cog center of gravity expressed in the body frame. In m. Shape [3].
                - cob center of boyency expressed in the body frame. In m. Shape [3].
                - rotItoB, rotational transform from inertial frame to the body frame. Shape [k, 3, 3]

        '''
        with tf.name_scope(scope) as scope:
            if use_sname:
                Fg = -self.mass * self.gravity * self.unit_z
                Fb = self.volume * self.density * self.gravity * self.unit_z
            else:
                Fg = self.mass * self.gravity * self.unit_z
                Fb = -self.volume * self.density * self.gravity * self.unit_z

            restoring = tf.concat([-1 * tf.matmul(tf.transpose(self._rotBtoI, perm=[0, 2, 1]), tf.expand_dims(Fg + Fb, axis=-1)), 
                            -1 * tf.matmul(tf.transpose(self._rotBtoI, perm=[0, 2, 1]), tf.expand_dims(tf.linalg.cross(self.cog, Fg) +
                                                                    tf.linalg.cross(self.cob, Fb), axis=-1))],
                            axis=1)
        return restoring

    def damping_matrix(self, scope, vel=None):
        '''
            Computes the damping matrix.

            input:
            ------
                - speed, the speed tensor shape [k, 6, 1]

            output:
            -------
                - $D(\nu)\nu$ the damping matrix. Shape [k, 6, 6]
        '''
        with tf.name_scope(scope) as scope:
            D = -1*self.linear_damping-tf.multiply(tf.expand_dims(vel[:, 0], axis=-1), self.linear_damping_forward_speed)
            tmp = -1 * tf.linalg.matmul(tf.expand_dims(self.quad_damping, axis=0), tf.abs(tf.linalg.diag(tf.squeeze(vel, axis=-1))))
            D = tf.add(D, tmp)
            return D

    def coriolis_matrix(self, scope, vel=None):
        '''
            Computes the coriolis matrix

            input:
            ------
                - speed, the speed tensor. Shape [k, 6]
            
            ouput:
            ------
                - $ C(\nu)\nu $ the coriolis matrix. Shape [k, 6, 6]
        '''
        k = vel.shape[0]
        with tf.name_scope(scope) as scope:

            O_pad = tf.zeros(shape=(k, 3, 3), dtype=tf.float64)

            S_12 = -tf_skew_op_k("Skew_coriolis",
                tf.squeeze(
                    tf.matmul(self._Mtot[0:3, 0:3], vel[:, 0:3]) +
                    tf.matmul(self._Mtot[0:3, 3:6], vel[:, 3:6])
                , axis=-1)
            )

            S_22 = -tf_skew_op_k("Skew_coriolis_diag",
                tf.squeeze(
                    tf.matmul(self._Mtot[3:6, 0:3], vel[:, 0:3]) +
                    tf.matmul(self._Mtot[3:6, 3:6], vel[:, 3:6])
                , axis=-1)
            )
            r1 = tf.concat([O_pad, S_12], axis=-1)
            r2 = tf.concat([S_12, S_22], axis=-1)
            C = tf.concat([r1, r2], axis=1)

            return C

    def acc(self, scope, vel, gen_forces=None, use_sname=True):
        with tf.name_scope(scope) as scope:
            tens_gen_forces = np.zeros(shape=(6, 1))
            if gen_forces is not None:
                tens_gen_forces = gen_forces
            
            D = self.damping_matrix("Damping", vel)
            C = self.coriolis_matrix("Coriolis", vel)
            g = self.restoring_forces("Restoring")

            self.invMtot = tf.linalg.inv(self._Mtot)

            rhs = tens_gen_forces - tf.matmul(C, vel) - tf.matmul(D, vel) - g
            lhs = tf.broadcast_to(self.invMtot, [self.k, 6, 6])

            acc = tf.matmul(lhs, rhs)

            return acc


def dummpy_plot():
    import matplotlib.pyplot as plt
    with open("/home/pierre/workspace/uuv_ws/src/mppi-ros/log/traj.npy", "rb") as f:
        traj = np.load(f)
    with open("/home/pierre/workspace/uuv_ws/src/mppi-ros/log/applied.npy", "rb") as f:
        applied = np.load(f)

    print(traj.shape)
    print(applied.shape)

    state_new = traj[:, 0, :, :]
    '''
    traj_plot = np.squeeze(traj)

    x = traj_plot[:, :, 0]
    y = traj_plot[:, :, 1]
    z = traj_plot[:, :, 2]

    r = traj_plot[:, :, 3]
    p = traj_plot[:, :, 4]
    ya = traj_plot[:, :, 5]

    vx = traj_plot[:, :, 6]
    vy = traj_plot[:, :, 7]
    vz = traj_plot[:, :, 8]

    vr = traj_plot[:, :, 9]
    vp = traj_plot[:, :, 10]
    vya = traj_plot[:, :, 11]

    shape = traj_plot.shape

    print(x.shape)
    print(y.shape)
    print(z.shape)

    #for i in range(shape[0]):
    #    ax.plot3D(x[i, :], y[i, :], z[i, :])

    # plt.show()


    fig, axs = plt.subplots(3, 2)
    for i in range(shape[0]):
        axs[0, 0].set_ylim(-50, 50)
        axs[0, 0].plot(x[i, :])

        axs[1, 0].set_ylim(-50, 50)
        axs[1, 0].plot(y[i, :])

        axs[2, 0].set_ylim(-50, 50)
        axs[2, 0].plot(z[i, :])

        axs[0, 1].set_ylim(-50, 50)
        axs[0, 1].plot(r[i, :])

        axs[1, 1].set_ylim(-50, 50)
        axs[1, 1].plot(p[i, :])

        axs[2, 1].set_ylim(-50, 50)
        axs[2, 1].plot(ya[i, :])


    fig1, axs1 = plt.subplots(3, 2)
    for i in range(shape[0]):

        axs1[0, 0].set_ylim(-50, 50)
        axs1[0, 0].plot(vx[i, :])


        axs1[0, 1].set_ylim(-50, 50)
        axs1[0, 1].plot(vy[i, :])


        axs1[1, 0].set_ylim(-50, 50)
        axs1[1, 0].plot(vz[i, :])


        axs1[1, 1].set_ylim(-50, 50)
        axs1[1, 1].plot(vr[i, :])


        axs1[2, 0].set_ylim(-50, 50)
        axs1[2, 0].plot(vp[i, :])


        axs1[2, 1].set_ylim(-50, 50)
        axs1[2, 1].plot(vya[i, :])


    applied_plot = np.squeeze(applied)

    fx = applied_plot[:, :, 0]
    fy = applied_plot[:, :, 1]
    fz = applied_plot[:, :, 2]

    tx = applied_plot[:, :, 3]
    ty = applied_plot[:, :, 4]
    tz = applied_plot[:, :, 5]

    shape = applied_plot.shape

    print(fx.shape)
    print(fy.shape)
    print(fz.shape)

    fig2, axs2 = plt.subplots(3, 2)
    for i in range(shape[0]):
        axs2[0, 0].plot(fx[i, :])
        axs2[0, 1].plot(fy[i, :])

        axs2[1, 0].plot(fz[i, :])

        axs2[1, 1].plot(tx[i, :])
        axs2[2, 0].plot(ty[i, :])
        axs2[2, 1].plot(tz[i, :])

    plt.show()
    '''
    pass

def main():

    params = dict()
    params["mass"] = 1862.87
    params["volume"] = 1.83826
    params["density"] = 1028.0
    params["height"] = 1.6
    params["length"] = 2.6
    params["width"] = 1.5
    params["cog"] = [0, 0, 0]
    params["cob"] = [0, 0, 0.3]
    params["Ma"] = [[779.79, -6.8773, -103.32,  8.5426, -165.54, -7.8033],
                    [-6.8773, 1222, 51.29, 409.44, -5.8488, 62.726],
                    [-103.32, 51.29, 3659.9, 6.1112, -386.42, 10.774],
                    [8.5426, 409.44, 6.1112, 534.9, -10.027, 21.019],
                    [-165.54, -5.8488, -386.42, -10.027,  842.69, -1.1162],
                    [-7.8033, 62.726, 10.775, 21.019, -1.1162, 224.32]]
    params["linear_damping"] = [-74.82, -69.48, -728.4, -268.8, -309.77, -105]
    params["quad_damping"] = [-748.22, -992.53, -1821.01, -672, -774.44, -523.27]
    params["linear_damping_forward_speed"] = [0., 0., 0., 0., 0., 0.]
    inertial = dict()
    inertial["ixx"] = 525.39
    inertial["iyy"] = 794.2
    inertial["izz"] = 691.23
    inertial["ixy"] = 1.44
    inertial["ixz"] = 33.41
    inertial["iyz"] = 2.6
    params["inertial"] = inertial
    auv_quat = AUVModel(quat=True, action_dim=6, dt=0.1, k=1, parameters=params)
    auv_euler = AUVModel(quat=False, action_dim=6, dt=0.1, k=1, parameters=params)


    print("*"*5 + " Initial state " + "*"*5)
    #fake input.
    fake_out_quat = np.array([[[0.], [0.], [0.], [1.], [0.], [0.], [0.], [1.], [0.], [0.], [0.], [0.], [0.]]])
    fake_out_euler = np.array([[[0.], [0.], [0.], [0.], [0.], [0.], [1.], [0.], [0.], [0.], [0.], [0.]]])
    fake_in = np.array([[[0.], [0.], [0.], [0.], [0.], [0.]]])

    for i in range(30):
        fake_out_euler = auv_euler.buildStepGraph("foo", fake_out_euler, fake_in)
        print(fake_out_euler)

        fake_out_quat = auv_quat.buildStepGraph("foo", fake_out_quat, fake_in)
        print(fake_out_quat)

        input()

if __name__ == "__main__":
    main()
