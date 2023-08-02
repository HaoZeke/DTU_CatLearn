"""Setup a generic kernel."""
import numpy as np


def general_kernel(features, dimension='single'):
    """Generate a default kernel."""
    length = default_lengthscale(features, dimension)

    return [
        {'type': 'linear', 'scaling': 1.0},
        {'type': 'constant', 'const': 1.0},
        {
            'type': 'gaussian',
            'width': length,
            'scaling': 1.0,
            'dimension': dimension,
        },
        {
            'type': 'quadratic',
            'slope': length,
            'degree': 1.0,
            'scaling': 1.0,
            'dimension': dimension,
        },
        {'type': 'laplacian', 'width': length, 'scaling': 1.0},
    ]


def default_lengthscale(features, dimension='single'):
    """Generate defaults for the kernel lengthscale.

    Parameters
    ----------
    features : array
        The feature matrix for the training data.
    dimension : str
        The number of parameters to return. Can be 'single', or 'features'.

    Returns
    -------
    std : array
        The standard deviation of the features.
    """
    msg = 'The dimension parameter must be "single" or "features"'
    assert dimension in ['single', 'features'], msg
    axis = 0 if dimension is not 'single' else None
    std = np.std(features, axis=axis)

    return std


def smooth_kernel(features, dimension='single'):
    """Generate a default kernel."""
    length = default_lengthscale(features, dimension)

    return [
        {
            'type': 'gaussian',
            'width': length,
            'scaling': 1.0,
            'dimension': dimension,
        }
    ]
