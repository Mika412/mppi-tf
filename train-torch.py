# General program to train a model using torch.
import argparse


def parse_args():
    parser = argparse.ArgumentParser(
        prog="train-network-torch",
        description="General program to train a network using torch."
    )
    parser.add_argument(
        'params', metavar='p', type=str,
        help='Yaml file containing the configuration for training.'
    )
    parser.add_argument(
        '-t', '--tf', action=argparse.BooleanOptionalAction,
        help='save the model as a tensorflow model (using onnx)'
    )
    parser.add_argument(
        '--save_dir', type=str, default="torch-training",
        help="saving directory for the model in it's different formats"
    )
    parser.add_argument(
        '-g', '--gpu', action=argparse.BooleanOptionalAction,
        help='Wether to train on gpu device or cpu')

    parser.add_argument(
        '-l', '--log', type=str,
        help='Log directory for the training.'
    )

    args = parser.parse_args()

    return args

args = parse_args()

import torch
import numpy as np
import pandas as pd
from torch.utils.tensorboard import SummaryWriter
import warnings
import os
from scripts.src_torch.models.auv_torch import VelPred
from scripts.src_torch.models.torch_utils import ListDataset, learn, save_model
from scripts.src.misc.utile import parse_config, npdtype
from tqdm import tqdm
from datetime import datetime

def get_model(config, device):
    type = config['model']['type']
    sDim = config['model']['sDim']
    aDim = config['model']['aDim']
    h = config['history']
    t = config['model']['topology']
    if type == 'velPred':
        return VelPred(in_size=h*(sDim-3+aDim), topology=t).to(device)

def get_optimizer(model, config):
    type = config['optimizer']['type']
    params = model.parameters()
    lr = config['optimizer']['lr']
    if type == 'adam':
        return torch.optim.Adam(params, lr=lr)

def get_loss(config, device):
    type = config['loss']['type']
    return torch.nn.MSELoss().to(device)

def get_train_params(config, device):
    return config['training_params']

def get_dataset(config, device):
    type = config['dataset']['type']
    data_dir = config['dataset']['dir']
    multi_dir = config['dataset']['multi_dir']
    multi_file = config['dataset']['multi_file']

    dfs = []
    if multi_dir:
        dirs = [d for d in os.listdir(data_dir) if os.path.isdir(os.path.join(data_dir, d))]
        for d in tqdm(dirs, desc="Directories", ncols=100, colour="green"):
            sub_dir = os.path.join(data_dir, d)
            files = [f for f in os.listdir(sub_dir) if os.path.isfile(os.path.join(sub_dir, f))]
            for f in tqdm(files, leave=False, desc=f"Dir {d}", ncols=100, colour="blue"):
                csv = os.path.join(sub_dir, f)
                df = pd.read_csv(csv)
                if 'x' not in df.columns:
                    print('\n' + csv)
                df = df.astype(npdtype)
                dfs.append(df)
    else:
        files = [f for f in os.listdir(data_dir) if os.path.isfile(os.path.join(data_dir, f))]
        for f in tqdm(files, desc=f"Dir {data_dir}", ncols=100, colour="blue"):
            csv = os.path.join(data_dir, f)
            df = pd.read_csv(csv)
            # TEMPORARY: used for current bluerov dataset that have those entries for some reason
            df = df.drop(['Time', 'header.seq', 'header.stamp.secs', 'header.stamp.nsecs', 'child_frame_id'], axis=1)
            if 'x' not in df.columns:
                print('\n' + csv)
            df = df.astype(npdtype)
            dfs.append(df)
    dataset = ListDataset(dfs, steps=config['steps'], history=config['history'], rot=config['dataset']['rot'])
    return dataset

def main():
    use_cuda = False
    if args.gpu:
        use_cuda = torch.cuda.is_available()
        if not use_cuda:
            warnings.warn("Asked for GPU but torch couldn't find a Cuda capable device")

    device = torch.device("cuda:0" if use_cuda else "cpu")

    config = parse_config(args.params)
    model = get_model(config, device)
    optim = get_optimizer(model, config)
    loss_fn = get_loss(config, device)
    train_params = get_train_params(config, device)
    dataset = get_dataset(config, device)
    epochs = config['epochs']
    h = config['history']
    steps = config['steps']

    ds = (
        torch.utils.data.DataLoader(
            dataset,
            **train_params), 
        None
    )

    writer = None
    if args.log is not None:
        writer = SummaryWriter(args.log)

    learn(ds, model, loss_fn, optim, writer, epochs, device)

    samples = 1

    dummy_state = torch.zeros((samples, h*(18-3))).to(device)
    dummy_action = torch.zeros((samples, h*6)).to(device)
    dummy_inputs = (dummy_state, dummy_action)
    input_names = ["x", "u"]
    output_names = ["vel"]
    dynamic_axes = {
        "x": {0: "kx"},
        "u": {0: "ku"},
        "vel": {0: "kv"}
    }

    stamp = datetime.now().strftime("%Y.%m.%d-%H:%M:%S")
    dir = os.path.join(args.save_dir, config['model_name'], stamp)

    if not os.path.exists(dir):
        os.makedirs(dir)

    save_model(
        model,
        dir=dir,
        tf=args.tf,
        dummy_input=dummy_inputs,
        input_names=input_names,
        output_names=output_names,
        dynamic_axes=dynamic_axes)



if __name__ == "__main__":
    main()