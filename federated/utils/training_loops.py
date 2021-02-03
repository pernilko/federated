import tensorflow as tf
import os
from federated.models.mitbih_model import create_dense_model
import time


def centralized_training_loop(
    model,
    dataset,
    name,
    epochs,
    output,
    decay_epochs=None,
    learning_rate_decay=0,
    save_model=True,
    validation_dataset=None,
    test_dataset=None,
):
    """
    Function trains a model on a dataset using centralized machine learning, and test its performance.
    Returns a history-object.
    """
    log_dir = os.path.join(output, "logdir", name)
    tf.io.gfile.makedirs(log_dir)

    callbacks = [
        tf.keras.callbacks.TensorBoard(log_dir=log_dir),
    ]

    if decay_epochs:

        def decay_fn(epoch, learning_rate):
            if epoch != 0 and epoch % decay_epochs == 0:
                return learning_rate * learning_rate_decay
            else:
                return learning_rate

        callbacks.append(tf.keras.callbacks.LearningRateScheduler(decay_fn, verbose=1))

    print("Training model")
    print(model.summary())

    start_time = time.time()
    history = model.fit(
        dataset,
        validation_data=validation_dataset,
        epochs=epochs,
        callbacks=callbacks,
    )
    end_time = time.time()

    if save_model:
        model.save(log_dir)

    if validation_dataset:
        validation_metrics = model.evaluate(validation_dataset, return_dict=True)
        print("Evaluating validation metrics")
        for m in model.metrics:
            print(f"\t{m.name}: {validation_metrics[m.name]:.4f}")

    if test_dataset:
        test_metrics = model.evaluate(test_dataset, return_dict=True)
        print("Evaluating test metrics")
        for m in model.metrics:
            print(f"\t{m.name}: {test_metrics[m.name]:.4f}")

    return history, end_time - start_time


def federated_training_loop(
    iterative_process,
    get_client_dataset,
    number_of_rounds,
    name,
    output,
    keras_model_fn=None,
    loss_fn=None,
    metrics_fn=None,
    validate_model=None,
    save_model=False,
):
    """
    Function trains a model on a dataset using federated learning.
    Returns its state.
    """

    log_dir = os.path.join(output, "logdir", name)
    train_log_dir = os.path.join(log_dir, "train")
    validation_log_dir = os.path.join(log_dir, "validation")

    tf.io.gfile.makedirs(log_dir)
    tf.io.gfile.makedirs(train_log_dir)
    tf.io.gfile.makedirs(validation_log_dir)

    initial_state = iterative_process.initialize()

    state = initial_state
    round_number = 0

    model_weights = iterative_process.get_model_weights(state)
    train_summary_writer = tf.summary.create_file_writer(train_log_dir)
    validation_summary_writer = tf.summary.create_file_writer(validation_log_dir)

    print("Model metrics:")

    round_times = []
    start_time = time.time()
    while round_number < number_of_rounds:
        round_start_time = time.time()
        print(f"Round number: {round_number}")
        federated_train_data = get_client_dataset(round_number)

        state, metrics = iterative_process.next(state, federated_train_data)
        with train_summary_writer.as_default():
            for name, value in metrics["train"].items():
                print(f"\t{name}: {value}")
                tf.summary.scalar(name, value, step=round_number)

        if validate_model:
            validation_metrics = validate_model(model_weights)
            with validation_summary_writer.as_default():
                for metric in validation_metrics:
                    value = validation_metrics[metric]
                    print(f"\tvalidation_{metric}: {value:.4f}")
                    tf.summary.scalar(metric, value, step=round_number)

        model_weights = iterative_process.get_model_weights(state)

        round_times.append(time.time() - round_start_time)

        round_number += 1

    end_time = time.time()
    avg_round_time = sum(round_times) / number_of_rounds

    if save_model:
        model = keras_model_fn()
        model.compile(
            loss=loss_fn(), optimizer=tf.keras.optimizers.SGD(), metrics=metrics_fn()
        )
        model_weights.assign_weights_to(model)
        model.save(log_dir)

    return state, end_time - start_time, avg_round_time