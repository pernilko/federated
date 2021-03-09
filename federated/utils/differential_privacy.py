import tensorflow as tf
import tensorflow_federated as tff


def gaussian_fixed_aggregation_factory(
    noise_multiplier: float, clients_per_round: int, clipping_value: float
) -> tff.aggregators.DifferentiallyPrivateFactory:

    """
    Function for differential privacy with fixed gaussian aggregation.
    Returns a `tff.aggregators.DifferentialPrivateFactory`
    """

    return tff.aggregators.DifferentiallyPrivateFactory.gaussian_fixed(
        noise_multiplier=noise_multiplier,
        clients_per_round=clients_per_round,
        clip=clipping_value,
    )


def gaussian_adaptive_aggregation_factory(
    noise_multiplier: float,
    clients_per_round: int,
    clipping_value: float,
    target_unclipped_quantile: float,
    learning_rate: float,
) -> tff.aggregators.DifferentiallyPrivateFactory:

    """
    Function for differential privacy with adaptive gaussian aggregation. The clipping rate is adaptive.
    Returns a `tff.aggregators.DifferentialPrivateFactory`
    """

    return tff.aggregators.DifferentiallyPrivateFactory.gaussian_adaptive(
        noise_multiplier=noise_multiplier,
        clients_per_round=clients_per_round,
        initial_l2_norm_clip=clipping_value,
        target_unclipped_quantile=target_unclipped_quantile,
        learning_rate=learning_rate,
    )
