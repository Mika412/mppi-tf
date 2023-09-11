import unittest
import torch
import pypose as pp

from scripts.utils.utils import tdtype
from scripts.inputs.ControllerInput import ControllerInput, ControllerInputPypose
from scripts.inputs.ModelInput import ModelInput, ModelInputPypose



class TestControllerInput(unittest.TestCase):
    def setUp(self):
        self.steps = 5
        self.pDim = 1
        self.vDim = 1
        self.aDim = 1
        self.input_module = ControllerInput(self.steps, self.pDim, self.vDim, self.aDim)

    def test_add_state(self):
        pose = torch.randn(self.pDim, dtype=tdtype)
        vel = torch.randn(self.vDim, dtype=tdtype)
        self.input_module.add_state(pose, vel)
        self.assertTrue(torch.all(torch.eq(self.input_module.poses[-1], pose)))
        self.assertTrue(torch.all(torch.eq(self.input_module.vels[-1], vel)))

    def test_add_act(self):
        action = torch.randn(self.aDim, dtype=tdtype)
        self.input_module.add_act(action)
        self.assertTrue(torch.all(torch.eq(self.input_module.actions[-1], action)))

    def test_add(self):
        pose = torch.randn(self.pDim, dtype=tdtype)
        vel = torch.randn(self.vDim, dtype=tdtype)
        action = torch.randn(self.aDim, dtype=tdtype)
        self.input_module.add(pose, vel, action)
        self.assertTrue(torch.all(torch.eq(self.input_module.poses[-1], pose)))
        self.assertTrue(torch.all(torch.eq(self.input_module.vels[-1], vel)))
        self.assertTrue(torch.all(torch.eq(self.input_module.actions[-1], action)))

    def test_get(self):
        k = 3
        poses, vels, actions = self.input_module.get(k)
        self.assertEqual(poses.shape, (k, self.steps, self.pDim))
        self.assertEqual(vels.shape, (k, self.steps, self.vDim))
        self.assertEqual(actions.shape, (k, self.steps - 1, self.aDim))

    def test_get_steps(self):
        self.assertEqual(self.input_module.get_steps(), self.steps)

    def test_is_init(self):
        self.assertFalse(self.input_module.is_init)
        for _ in range(self.steps - 1):
            self.input_module.add(torch.randn(self.pDim, dtype=tdtype),
                                  torch.randn(self.vDim, dtype=tdtype),
                                  torch.randn(self.aDim, dtype=tdtype))
        self.assertFalse(self.input_module.is_init)
        self.input_module.add_state(torch.randn(self.pDim, dtype=tdtype),
                                    torch.randn(self.vDim, dtype=tdtype))
        self.assertTrue(self.input_module.is_init)


class TestModelInput(unittest.TestCase):
    def setUp(self):
        self.k = 3
        self.steps = 5
        self.pDim = 7
        self.vDim = 6
        self.aDim = 6

        self.controller_input = ControllerInput(self.steps, self.pDim, self.vDim, self.aDim)
        for _ in range(self.steps - 1):
            self.controller_input.add(torch.randn(self.pDim),
                                      torch.randn(self.vDim),
                                      torch.randn(self.aDim))
        self.controller_input.add_state(torch.randn(self.pDim),
                                        torch.randn(self.vDim))
        
        self.model_input = ModelInput(self.k, self.steps, self.pDim, self.vDim, self.aDim)

    def test_init(self):
        self.model_input.init(self.controller_input)
        self.assertEqual(self.model_input.poses.shape, (self.k, self.steps, self.pDim))
        self.assertEqual(self.model_input.vels.shape, (self.k, self.steps, self.vDim))
        self.assertEqual(self.model_input.actions.shape, (self.k, self.steps, self.aDim))

    def test_forward(self):
        action = torch.randn(self.k, self.aDim, dtype=tdtype)
        poses, vels, actions = self.model_input(action)
        self.assertEqual(poses.shape, (self.k, self.steps, self.pDim))
        self.assertEqual(vels.shape, (self.k, self.steps, self.vDim))
        self.assertEqual(actions.shape, (self.k, self.steps, self.aDim))
        self.assertTrue(torch.all(torch.eq(self.model_input.actions[:, -1], action)))

    def test_update(self):
        new_pose = torch.randn(self.k, 1, self.pDim, dtype=tdtype)
        new_vel = torch.randn(self.k, 1, self.vDim, dtype=tdtype)
        self.model_input.update(new_pose, new_vel)
        self.assertTrue(torch.all(torch.eq(self.model_input.poses[:, -1:], new_pose)))
        self.assertTrue(torch.all(torch.eq(self.model_input.vels[:, -1:], new_vel)))


class TestControllerInputSteps1(unittest.TestCase):
    def setUp(self):
        self.steps = 1
        self.pDim = 7
        self.vDim = 6
        self.aDim = 6
        self.input_module = ControllerInput(self.steps, self.pDim, self.vDim, self.aDim)

    def test_add_state(self):
        pose = torch.randn(self.pDim, dtype=tdtype)
        vel = torch.randn(self.vDim, dtype=tdtype)
        self.input_module.add_state(pose, vel)
        self.assertTrue(torch.all(torch.eq(self.input_module.poses[-1], pose)))
        self.assertTrue(torch.all(torch.eq(self.input_module.vels[-1], vel)))

    def test_add_act(self):
        action = torch.randn(self.aDim, dtype=tdtype)
        self.input_module.add_act(action)
        with self.assertRaises(IndexError):
            element = self.input_module.actions[-1]

    def test_add(self):
        pose = torch.randn(self.pDim, dtype=tdtype)
        vel = torch.randn(self.vDim, dtype=tdtype)
        action = torch.randn(self.aDim, dtype=tdtype)
        self.input_module.add(pose, vel, action)
        self.assertTrue(torch.all(torch.eq(self.input_module.poses[-1], pose)))
        self.assertTrue(torch.all(torch.eq(self.input_module.vels[-1], vel)))
        with self.assertRaises(IndexError):
            element = self.input_module.actions[-1]

    def test_get(self):
        k = 3
        poses, vels, actions = self.input_module.get(k)
        self.assertEqual(poses.shape, (k, self.steps, self.pDim))
        self.assertEqual(vels.shape, (k, self.steps, self.vDim))
        self.assertEqual(actions.shape, (k, self.steps - 1, self.aDim))

    def test_get_steps(self):
        self.assertEqual(self.input_module.get_steps(), self.steps)

    def test_is_init(self):
        self.assertFalse(self.input_module.is_init)
        for _ in range(self.steps - 1):
            self.input_module.add(torch.randn(self.pDim, dtype=tdtype),
                                  torch.randn(self.vDim, dtype=tdtype),
                                  torch.randn(self.aDim, dtype=tdtype))
        self.assertFalse(self.input_module.is_init)
        self.input_module.add_state(torch.randn(self.pDim, dtype=tdtype),
                                    torch.randn(self.vDim, dtype=tdtype))
        self.assertTrue(self.input_module.is_init)


class TestModelInputSteps1(unittest.TestCase):
    def setUp(self):
        self.k = 3
        self.steps = 1
        self.pDim = 7
        self.vDim = 6
        self.aDim = 6

        self.controller_input = ControllerInput(self.steps, self.pDim, self.vDim, self.aDim)

        self.controller_input.add_state(torch.randn(self.pDim),
                                        torch.randn(self.vDim))
        
        self.model_input = ModelInput(self.k, self.steps, self.pDim, self.vDim, self.aDim)
        self.model_input.init(self.controller_input)

    def test_init(self):
        self.assertEqual(self.model_input.poses.shape, (self.k, self.steps, self.pDim))
        self.assertEqual(self.model_input.vels.shape, (self.k, self.steps, self.vDim))
        self.assertEqual(self.model_input.actions.shape, (self.k, self.steps, self.aDim))
        self.assertTrue(torch.all(torch.eq(self.model_input.actions, torch.zeros(self.k, self.steps, self.aDim))))

    def test_forward(self):
        action = torch.randn(self.k, self.aDim, dtype=tdtype)
        poses, vels, actions = self.model_input(action)
        self.assertEqual(poses.shape, (self.k, self.steps, self.pDim))
        self.assertEqual(vels.shape, (self.k, self.steps, self.vDim))
        self.assertEqual(actions.shape, (self.k, self.steps, self.aDim))
        self.assertTrue(torch.all(torch.eq(self.model_input.actions[:, -1], action)))

    def test_update(self):
        new_pose = torch.randn(self.k, 1, self.pDim, dtype=tdtype)
        new_vel = torch.randn(self.k, 1, self.vDim, dtype=tdtype)
        self.model_input.update(new_pose, new_vel)
        self.assertTrue(torch.all(torch.eq(self.model_input.poses[:, -1:], new_pose)))
        self.assertTrue(torch.all(torch.eq(self.model_input.vels[:, -1:], new_vel)))


# PYPOSE SECITON
class TestControllerInputPypose(unittest.TestCase):
    def setUp(self):
        self.steps = 5
        self.aDim = 6
        self.input_module = ControllerInputPypose(self.steps, self.aDim)

    def test_add_state(self):
        state = torch.tensor([0.1, 0.2, 3.0, 0.0, 0.0, 0.0, 1.0,
                              1.2, 2.1, 3.1, 1.3, 4.5, 5.4], dtype=tdtype)
        self.input_module.add_state(state)
        self.assertTrue(torch.all(torch.eq(self.input_module.poses[-1], state[:7])))
        self.assertTrue(torch.all(torch.eq(self.input_module.vels[-1], state[7:])))

    def test_add_act(self):
        action = torch.randn(self.aDim, dtype=tdtype)
        self.input_module.add_act(action)
        self.assertTrue(torch.all(torch.eq(self.input_module.actions[-1], action)))

    def test_add(self):
        state = torch.tensor([0.1, 0.2, 3.0, 0.0, 0.0, 0.0, 1.0,
                              1.2, 2.1, 3.1, 1.3, 4.5, 5.4], dtype=tdtype)
        action = torch.randn(self.aDim, dtype=tdtype)
        self.input_module.add(state, action)
        self.assertTrue(torch.all(torch.eq(self.input_module.poses[-1], state[:7])))
        self.assertTrue(torch.all(torch.eq(self.input_module.vels[-1], state[7:])))
        self.assertTrue(torch.all(torch.eq(self.input_module.actions[-1], action)))

    def test_get(self):
        k = 3
        poses, vels, actions = self.input_module.get(k)
        self.assertEqual(poses.shape, (k, self.steps, 7))
        self.assertEqual(vels.shape, (k, self.steps, 6))
        self.assertEqual(actions.shape, (k, self.steps - 1, self.aDim))

    def test_get_steps(self):
        self.assertEqual(self.input_module.get_steps(), self.steps)

    def test_is_init(self):
        state = torch.tensor([0.1, 0.2, 3.0, 0.0, 0.0, 0.0, 1.0,
                              1.2, 2.1, 3.1, 1.3, 4.5, 5.4], dtype=tdtype)
        self.assertFalse(self.input_module.is_init)
        for _ in range(self.steps - 1):
            self.input_module.add(state,
                                  torch.randn(self.aDim, dtype=tdtype))
        self.assertFalse(self.input_module.is_init)
        self.input_module.add_state(state)
        self.assertTrue(self.input_module.is_init)


class TestModelInputPypose(unittest.TestCase):
    def setUp(self):
        self.k = 3
        self.steps = 5
        self.aDim = 6
        self.fake_state = torch.tensor([0.1, 0.2, 3.0, 0.0, 0.0, 0.0, 1.0,
                                        1.2, 2.1, 3.1, 1.3, 4.5, 5.4], dtype=tdtype)

        self.controller_input = ControllerInputPypose(self.steps, self.aDim)
        for _ in range(self.steps - 1):
            self.controller_input.add(self.fake_state, 
                                      torch.randn(self.aDim, dtype=tdtype))
        self.controller_input.add_state(self.fake_state)

        self.model_input = ModelInputPypose(self.k, self.steps, self.aDim)
        self.model_input.init(self.controller_input)

    def test_init(self):
        self.assertEqual(self.model_input.poses.shape, (self.k, self.steps, 7))
        self.assertEqual(self.model_input.vels.shape, (self.k, self.steps, 6))
        self.assertEqual(self.model_input.actions.shape, (self.k, self.steps, self.aDim))

    def test_forward(self):
        action = torch.randn(self.k, self.aDim, dtype=tdtype)
        poses, vels, actions = self.model_input(action)
        self.assertEqual(poses.shape, (self.k, self.steps, 7))
        self.assertEqual(vels.shape, (self.k, self.steps, 6))
        self.assertEqual(actions.shape, (self.k, self.steps, self.aDim))
        self.assertTrue(torch.all(torch.eq(self.model_input.actions[:, -1], action)))

    def test_update(self):
        new_pose = pp.randn_SE3(self.k, 1, dtype=tdtype)
        new_vel = torch.randn(self.k, 1, 6, dtype=tdtype)
        old_act = self.model_input.actions.clone()
        self.model_input.update(new_pose, new_vel)
        self.assertTrue(torch.all(torch.eq(self.model_input.poses[:, -1:], new_pose)))
        self.assertTrue(torch.all(torch.eq(self.model_input.vels[:, -1:], new_vel)))
        self.assertTrue(torch.all(torch.eq(self.model_input.actions[:, -1], old_act[:, 0])))


class TestControllerInputPyposeSteps1(unittest.TestCase):
    def setUp(self):
        self.steps = 1
        self.aDim = 6
        self.input_module = ControllerInputPypose(self.steps, self.aDim)

    def test_add_state(self):
        state = torch.tensor([0.1, 0.2, 3.0, 0.0, 0.0, 0.0, 1.0,
                              1.2, 2.1, 3.1, 1.3, 4.5, 5.4], dtype=tdtype)
        self.input_module.add_state(state)
        self.assertTrue(torch.all(torch.eq(self.input_module.poses[-1], state[:7])))
        self.assertTrue(torch.all(torch.eq(self.input_module.vels[-1], state[7:])))

    def test_add_act(self):
        action = torch.randn(self.aDim, dtype=tdtype)
        self.input_module.add_act(action)
        with self.assertRaises(IndexError):
            element = self.input_module.actions[-1]

    def test_add(self):
        state = torch.tensor([0.1, 0.2, 3.0, 0.0, 0.0, 0.0, 1.0,
                              1.2, 2.1, 3.1, 1.3, 4.5, 5.4], dtype=tdtype)
        action = torch.randn(self.aDim, dtype=tdtype)
        self.input_module.add(state, action)
        self.assertTrue(torch.all(torch.eq(self.input_module.poses[-1], state[:7])))
        self.assertTrue(torch.all(torch.eq(self.input_module.vels[-1], state[7:])))
        with self.assertRaises(IndexError):
            element = self.input_module.actions[-1]

    def test_get(self):
        k = 3
        poses, vels, actions = self.input_module.get(k)
        self.assertEqual(poses.shape, (k, self.steps, 7))
        self.assertEqual(vels.shape, (k, self.steps, 6))
        self.assertEqual(actions.shape, (k, self.steps - 1, self.aDim))

    def test_get_steps(self):
        self.assertEqual(self.input_module.get_steps(), self.steps)

    def test_is_init(self):
        state = torch.tensor([0.1, 0.2, 3.0, 0.0, 0.0, 0.0, 1.0,
                              1.2, 2.1, 3.1, 1.3, 4.5, 5.4], dtype=tdtype)
        self.assertFalse(self.input_module.is_init)
        for _ in range(self.steps - 1):
            self.input_module.add(state,
                                  torch.randn(self.aDim, dtype=tdtype))
        self.assertFalse(self.input_module.is_init)
        self.input_module.add_state(state)
        self.assertTrue(self.input_module.is_init)


class TestModelInputPyposeSteps1(unittest.TestCase):
    def setUp(self):
        self.k = 3
        self.steps = 1
        self.sDim = 13
        self.aDim = 6
        self.fake_state = torch.tensor([0.1, 0.2, 3.0, 0.0, 0.0, 0.0, 1.0,
                                        1.2, 2.1, 3.1, 1.3, 4.5, 5.4], dtype=tdtype)
        self.controller_input = ControllerInputPypose(self.steps, self.aDim)

        self.controller_input.add_state(self.fake_state)
        
        self.model_input = ModelInputPypose(self.k, self.steps, self.aDim)
        self.model_input.init(self.controller_input)

    def test_init(self):
        self.assertEqual(self.model_input.poses.shape, (self.k, self.steps, 7))
        self.assertEqual(self.model_input.vels.shape, (self.k, self.steps, 6))
        self.assertEqual(self.model_input.actions.shape, (self.k, self.steps, self.aDim))
        self.assertTrue(torch.all(torch.eq(self.model_input.actions, torch.zeros(self.k, self.steps, self.aDim))))

    def test_forward(self):
        action = torch.randn(self.k, self.aDim, dtype=tdtype)
        poses, vels, actions = self.model_input(action)
        self.assertEqual(poses.shape, (self.k, self.steps, 7))
        self.assertEqual(vels.shape, (self.k, self.steps, 6))
        self.assertEqual(actions.shape, (self.k, self.steps, self.aDim))
        self.assertTrue(torch.all(torch.eq(self.model_input.actions[:, -1], action)))

    def test_update(self):
        new_pose = pp.randn_SE3(self.k, 1, dtype=tdtype)
        new_vel = torch.randn(self.k, 1, 6, dtype=tdtype)
        old_act = self.model_input.actions.clone()
        self.model_input.update(new_pose, new_vel)
        self.assertTrue(torch.all(torch.eq(self.model_input.poses[:, -1:], new_pose)))
        self.assertTrue(torch.all(torch.eq(self.model_input.vels[:, -1:], new_vel)))
        self.assertTrue(torch.all(torch.eq(self.model_input.actions[:, -1], old_act[:, 0])))



if __name__ == '__main__':
    unittest.main()