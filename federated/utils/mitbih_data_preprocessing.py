import collections

import tensorflow as tf
import pandas as pd
import tensorflow_federated as tff
import numpy as np
import collections
from keras.utils.np_utils import to_categorical

from sklearn.utils import resample

SAMPLES = 20_000


def _preprocess_dataframe(df):
    """
    Function seperates label column from datapoints columns.
    Returns tuple: dataframe without label, labels

    """
    label = df[df.columns[-1]]
    df.drop(df.columns[-1], axis=1, inplace=True)
    return df, label


def create_dataset(X, y):
    """
    Function converts pandas dataframe to tensorflow federated.
    Returns dataset of type tff.simulation.ClientData
    """
    num_of_clients = 10
    total_ecg_count = len(X)
    ecgs_per_set = int(np.floor(total_ecg_count / num_of_clients))

    client_dataset = collections.OrderedDict()
    for i in range(1, num_of_clients + 1):
        name_of_client = f"client_{i}"
        start = ecgs_per_set * (i - 1)
        end = ecgs_per_set * i

        data = collections.OrderedDict(
            (("label", y[start:end]), ("datapoints", X[start:end]))
        )
        client_dataset[name_of_client] = data

    return tff.simulation.FromTensorSlicesClientData(client_dataset)


def _preprocess_dataframe(df):
    df[187] = df[187].astype(int)
    target = df[df.columns[-1]]
    df.drop(df.columns[-1], axis=1, inplace=True)
    return df, target


def load_data(centralized=False):
    """
    Function loads data from csv-file
    and preprocesses the training and test data seperately.
    Returns a tuple of tff.simulation.ClientData
    """
    train_df = pd.read_csv("data/mitbih/mitbih_train.csv", header=None)
    test_df = pd.read_csv("data/mitbih/mitbih_test.csv", header=None)

    train_df[187], test_df[187] = (
        train_df[187].astype(int),
        test_df[187].astype(int),
    )

    if centralized:
        # From the data analysis, we can see that the normal heartbeats are over represented in the dataset
        df_0 = (train_df[train_df[187] == 0]).sample(n=SAMPLES, random_state=42)
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

    train_X, train_y = _preprocess_dataframe(train_df)
    test_X, test_y = _preprocess_dataframe(test_df)

    train_y, test_y = (
        to_categorical(train_y).astype(int),
        to_categorical(test_y).astype(int),
    )

    return create_dataset(train_X, train_y), create_dataset(test_X, test_y)


def preprocess_dataset(epochs, batch_size, shuffle_buffer_size):
    """
    Function returns a function for preprocessing of a dataset
    """

    def _reshape(element):
        """
        Function returns reshaped tensors
        """

        return (tf.expand_dims(element["datapoints"], axis=-1), element["label"])

    @tff.tf_computation(
        tff.SequenceType(
            collections.OrderedDict(
                label=tff.TensorType(tf.int64, shape=(5,)),
                datapoints=tff.TensorType(tf.float64, shape=(187,)),
            )
        )
    )
    def preprocess(dataset):
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


def get_centralized_datasets(
    train_batch_size=32,
    test_batch_size=32,
    train_shuffle_buffer_size=1000,
    test_shuffle_buffer_size=1000,
    epochs=1,
):

    """
    Function preprocesses datasets.
    Return input-ready datasets
    """
    train_dataset, test_dataset = load_data(centralized=True)
    train_dataset, test_dataset = (
        train_dataset.create_tf_dataset_from_all_clients(),
        test_dataset.create_tf_dataset_from_all_clients(),
    )

    train_preprocess = preprocess_dataset(
        epochs=epochs,
        batch_size=train_batch_size,
        shuffle_buffer_size=train_shuffle_buffer_size,
    )

    test_preprocess = preprocess_dataset(
        epochs=epochs,
        batch_size=test_batch_size,
        shuffle_buffer_size=test_shuffle_buffer_size,
    )

    train_dataset = train_preprocess(train_dataset)
    test_dataset = test_preprocess(test_dataset)

    return train_dataset, test_dataset