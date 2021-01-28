# Implementation of Information theoretic Model Predictive Control for Model Based Reinforcement learning.

## dependencies

Relies on tensorflow c++ API r2.1. If you don't want to mess with bazel, use [tensorflowCC](https://github.com/FloopCZ/tensorflow_cc) which provides a cmake version of compilling tensorflow.

    ```bash
    --config=cuda //tensorflow:libtensorflow_cc.so //tensorflow:libtensorflow_framework.so //tensorflow:install_headers -j 4 --noincompatible_do_not_split_linking_cmdline
    ```

## Installation

    ```bash
        mkdir build & cd build
        cmake ..
        make
    ```
