"""Setup k-fold array split for cross validation."""
import numpy as np
import json
import pickle


def k_fold(features, targets=None, nsplit=3, fix_size=None):
    """Routine to split feature matrix and return sublists.

    Parameters
    ----------
    features : array
        An n, d feature array.
    targets : list
        A list to target values.
    nsplit : int
        The number of bins that data should be devided into.
    fix_size : int
        Define a fixed sample size, e.g. nsplit=5 fix_size=100, generates
        5 x 100 data split. Default is None, all available data is divided
        nsplit times.

    Returns
    -------
    features : list
        A list of feature arrays of length nsplit.
    targets : list
        A list of targets lists of length nsplit.
    """
    # Stick features and targets together.
    if targets is not None:
        d, f = np.shape(features)
        X = np.concatenate(
            (features, np.reshape(targets, (len(targets), 1))), axis=1)
        assert (d, f + 1) == np.shape(X)
    else:
        X = features

    # Shuffle the combined array.
    np.random.shuffle(X)  # Shuffle ordering of the array along 0 axis.

    if fix_size is not None:
        msg = (
            'Cannot divide dataset in this way, number of candidates is '
            + 'too small'
        )
        assert np.shape(X)[0] >= nsplit * fix_size, msg

        X = X[:nsplit * fix_size, :]

    # Split the feature-targets array.
    X = np.array_split(X, nsplit)

    if targets is not None:
        # Split the features and targets, generating two lists.
        features, targets = [], []
        for i in X:
            features.append(i[:, :-1])
            targets.append(i[:, -1])

        return features, targets
    else:
        features = list(X)
        return features


def write_split(features, targets, fname, fformat='pickle'):
    """Function to write the k-fild split to file.

    Parameters
    ----------
    features : array
        An n, d feature array.
    targets : list
        A list to target values.
    fname : str
        The name of the write file.
    fformat : str
        File format to write to. Can be json or pickle, default is pickle.
    """
    data = {'features': features, 'targets': targets}

    if fformat == 'json':
        seralized_features = [f.tolist() for f in features]
        data['features'] = seralized_features

        seralized_targets = [t.tolist() for t in targets]
        data['targets'] = seralized_targets

        with open(f'{fname}.json', 'w') as textfile:
            json.dump(data, textfile)

    elif fformat == 'pickle':
        with open(f'{fname}.pickle', 'wb') as textfile:
            pickle.dump(data, textfile, protocol=pickle.HIGHEST_PROTOCOL)

    else:
        raise NotImplementedError(f'{fformat} format not supported')


def read_split(fname, fformat='pickle'):
    """Function to read the k-fold split from file.

    Parameters
    ----------
    fname : str
        The name of the read file.
    fformat : str
        File format to read from. Can be json or pickle, default is pickle.

    Returns
    -------
    features : list
        A list of feature arrays of length nsplit.
    targets : list
        A list of targets lists of length nsplit.
    """
    if fformat == 'json':
        with open(f'{fname}.json', 'r') as textfile:
            data = json.load(textfile)
    elif fformat == 'pickle':
        with open(f'{fname}.pickle', 'rb') as textfile:
            data = pickle.load(textfile)
    else:
        raise NotImplementedError(f'{fformat} format not supported')

    features, targets = data['features'], data['targets']

    # Convert JSON output back to numpy arrays.
    if fformat == 'json':
        features_reformat = [np.asarray(f) for f in features]
        targets_reformat = [np.asarray(t) for t in targets]
        features, targets = features_reformat, targets_reformat

    return features, targets
