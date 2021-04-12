import collections
import functools
import pickle
import random
from typing import Callable, Dict, List

import numpy as np
import pandas as pd
import tensorflow as tf
import tensorflow_federated as tff
from tensorflow.keras.utils import to_categorical
from sklearn.utils import resample

SAMPLES = 20_000
NUM_OF_CLIENTS = 10
S = 100

"""
Function seperates label column from datapoints columns.
Returns tuple: dataframe without label, labels
"""
split_dataframe = lambda df: (
    df.iloc[:, :186].values,
    to_categorical(df[187]).astype(int),
)


def create_dataset(
    X: np.ndarray, y: np.ndarray, number_of_clients: int
) -> [None, tff.simulation.ClientData]:
    """
    Function converts pandas dataframe to tensorflow federated.
    Returns dataset of type tff.simulation.ClientData
    """
    num_of_clients = NUM_OF_CLIENTS
    total_ecg_count = len(X)
    ecgs_per_set = int(np.floor(total_ecg_count / num_of_clients))

    client_dataset = collections.OrderedDict()
    for i in range(1, num_of_clients + 1):
        name_of_client = f"client_{i}"
        start = ecgs_per_set * (i - 1)
        end = ecgs_per_set * i
        data = collections.OrderedDict(
            (
                ("label", np.array(y[start:end], dtype=np.int32)),
                ("datapoints", np.array(X[start:end], dtype=np.float32)),
            )
        )
        client_dataset[name_of_client] = data

    return None, tff.simulation.FromTensorSlicesClientData(client_dataset)


def create_tff_dataset(clients_data: Dict) -> tff.simulation.ClientData:

    """
    Function creates a tensorflow federated dataset from a dictionary that contains the data for the different clients.
    """

    client_dataset = collections.OrderedDict()

    for client in clients_data:
        data = collections.OrderedDict(
            (
                ("label", np.array(clients_data[client][1], dtype=np.int32)),
                ("datapoints", np.array(clients_data[client][0], dtype=np.float32)),
            )
        )
        client_dataset[client] = data

    return tff.simulation.FromTensorSlicesClientData(client_dataset)


def create_class_distributed_dataset(
    X: np.ndarray, y: np.ndarray, number_of_clients: int
) -> [Dict, tff.simulation.ClientData]:

    """
    Function distributes the data in a way such that each client gets one type of data.
    Returns a dictionary and a tensorflow federated dataset containing the distributed dataset.
    """
    n = len(X)
    clients_data = {f"client_{i}": [[], []] for i in range(1, 6)}

    for i in range(n):
        index = np.where(y[i] == 1)[0][0]
        clients_data[f"client_{index+1}"][0].append(X[i])
        clients_data[f"client_{index+1}"][1].append(y[i])

    return clients_data, create_tff_dataset(clients_data)


def create_uniform_dataset(
    X: np.ndarray, y: np.ndarray, number_of_clients: int
) -> [Dict, tff.simulation.ClientData]:

    """
    Function distributes the data equally such that each client holds equal amounts of each class.
    """
    clients_data = {f"client_{i}": [[], []] for i in range(1, number_of_clients + 1)}
    for i in range(len(X)):
        clients_data[f"client_{(i%number_of_clients)+1}"][0].append(X[i])
        clients_data[f"client_{(i%number_of_clients)+1}"][1].append(y[i])

    return clients_data, create_tff_dataset(clients_data)


def create_unbalanced_data(
    X: np.ndarray, y: np.ndarray, number_of_clients: int
) -> [Dict, tff.simulation.ClientData]:

    """
    Function distributes the data in such a way that one client only has one type of data,
    while the rest of the clients has non-iid data.
    """
    indices = np.arange(X.shape[0])
    np.random.shuffle(indices)
    X = X[indices]
    y = y[indices]

    clients_data = {f"client_{i}": [[], []] for i in range(1, number_of_clients + 1)}
    for i in range(len(X)):
        if np.where(y[i] == 1)[0][0] == 0:
            clients_data[f"client_{1}"][0].append(X[i])
            clients_data[f"client_{1}"][1].append(y[i])
        else:
            client = random.choice([i for i in range(1, 6) if i not in [1]])
            clients_data[f"client_{client}"][0].append(X[i])
            clients_data[f"client_{client}"][1].append(y[i])

    return clients_data, create_tff_dataset(clients_data)


def create_non_iid_dataset(
    X: np.ndarray, y: np.ndarray, number_of_clients: int
) -> [Dict, tff.simulation.ClientData]:

    """
    Function distributes the data such that each client has non-iid data.
    """
    indices = np.arange(X.shape[0])
    np.random.shuffle(indices)
    X = X[indices]
    y = y[indices]

    clients_data = {f"client_{i}": [[], []] for i in range(1, number_of_clients + 1)}
    for i in range(len(X)):
        client = random.randrange(
            1, number_of_clients + 1, np.random.randint(1, number_of_clients + 1)
        )
        clients_data[f"client_{client}"][0].append(X[i])
        clients_data[f"client_{client}"][1].append(y[i])

    return clients_data, create_tff_dataset(clients_data)


def load_data(
    normalized: bool = True,
    data_analysis: bool = False,
    data_selector: Callable[
        [np.ndarray, np.ndarray, int], tff.simulation.ClientData
    ] = None,
    number_of_clients: int = 5,
    save_data: bool = False,
) -> [tff.simulation.ClientData, tff.simulation.ClientData, int]:
    """
    Function loads data from csv-file
    and preprocesses the training and test data seperately.
    Returns a tuple of tff.simulation.ClientData
    """
    train_file = "data/mitbih/mitbih_train.csv"
    test_file = "data/mitbih/mitbih_test.csv"

    if data_analysis or data_selector == create_unbalanced_data:
        train_file = "../" + train_file
        test_file = "../" + test_file

    train_df = pd.read_csv(train_file, header=None)
    test_df = pd.read_csv(test_file, header=None)

    train_df[187], test_df[187] = (
        train_df[187].astype(int),
        test_df[187].astype(int),
    )

    if normalized:
        df_0 = (train_df[train_df[187] == 0]).sample(n=SAMPLES, random_state=42)
        # df_5 = (train_df[train_df[187] == 4]).sample(n=S, random_state=42)
        train_df = pd.concat(
            [df_0]
            + [
                resample(
                    train_df[train_df[187] == i],
                    replace=True,
                    n_samples=SAMPLES,
                    random_state=int(f"12{i+2}"),
                )
                for i in range(1, 5)
            ]
        )

    train_X, train_y = split_dataframe(train_df)

    test_X, test_y = split_dataframe(test_df)

    if data_analysis:
        return test_X, test_y

    if data_selector == create_uniform_dataset:
        if not normalized:
            raise ValueError(
                "The data has to be normalized to use create_uniform_dataset"
            )

    train_client_data, train_data = data_selector(train_X, train_y, number_of_clients)
    test_client_data, test_data = data_selector(test_X, test_y, number_of_clients)

    if data_selector == create_unbalanced_data:
        return train_client_data, test_client_data

    if save_data:
        f = open("history/logdir/data_distributions", "ab")
        pickle.dump(train_client_data, f)
        pickle.dump(test_client_data, f)
        f.close()

    return train_data, test_data, len(train_X)


def preprocess_dataset(
    epochs: int, batch_size: int, shuffle_buffer_size: int
) -> Callable[[tf.data.Dataset], tf.data.Dataset]:
    """
    Function returns a function for preprocessing of a dataset
    """

    def _reshape(element: collections.OrderedDict) -> tf.Tensor:
        """
        Function returns reshaped tensors
        """

        return (tf.expand_dims(element["datapoints"], axis=-1), element["label"])

    @tff.tf_computation(
        tff.SequenceType(
            collections.OrderedDict(
                label=tff.TensorType(tf.int32, shape=(5,)),
                datapoints=tff.TensorType(tf.float32, shape=(186,)),
            )
        )
    )
    def preprocess(dataset: tf.data.Dataset) -> tf.data.Dataset:
        """
        Function returns shuffled dataset
        """
        return (
            dataset.shuffle(shuffle_buffer_size)
            .repeat(epochs)
            .batch(batch_size, drop_remainder=False)
            .map(_reshape, num_parallel_calls=tf.data.experimental.AUTOTUNE)
        )

    return preprocess


def get_datasets(
    train_batch_size: int = 32,
    test_batch_size: int = 32,
    train_shuffle_buffer_size: int = 10000,
    test_shuffle_buffer_size: int = 10000,
    train_epochs: int = 5,
    test_epochs: int = 5,
    centralized: bool = False,
    normalized: bool = True,
    data_selector: Callable[
        [np.ndarray, np.ndarray, int], tff.simulation.ClientData
    ] = create_dataset,
    number_of_clients: int = 5,
    save_data: bool = False,
):

    """
    Function preprocesses datasets.
    Return input-ready datasets
    """
    train_dataset, test_dataset, n = load_data(
        normalized=normalized,
        data_selector=data_selector,
        number_of_clients=number_of_clients,
        save_data=save_data,
    )

    if centralized:
        train_dataset, test_dataset = (
            train_dataset.create_tf_dataset_from_all_clients(),
            test_dataset.create_tf_dataset_from_all_clients(),
        )

    train_preprocess = preprocess_dataset(
        epochs=train_epochs,
        batch_size=train_batch_size,
        shuffle_buffer_size=train_shuffle_buffer_size,
    )

    test_preprocess = preprocess_dataset(
        epochs=test_epochs,
        batch_size=test_batch_size,
        shuffle_buffer_size=test_shuffle_buffer_size,
    )

    if centralized:
        train_dataset = train_preprocess(train_dataset)
        test_dataset = test_preprocess(test_dataset)
    else:
        train_dataset = train_dataset.preprocess(train_preprocess)
        test_dataset = test_dataset.preprocess(test_preprocess)

    return (train_dataset, test_dataset, n)