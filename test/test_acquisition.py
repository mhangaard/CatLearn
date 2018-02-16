"""Script to test the acquisition functions."""
from __future__ import print_function
from __future__ import absolute_import

import os

from ase.ga.data import DataConnection

from atoml.utilities.data_setup import get_unique, get_train
from atoml.fingerprint.setup import return_fpv
from atoml.fingerprint import ParticleFingerprintGenerator
from atoml.regression import GaussianProcess
from atoml.utilities.acquisition_functions import AcquisitionFunctions

wkdir = os.getcwd()

train_size, test_size = 45, 5


def classifier(atoms):
    """Simple function to classify atoms objects."""
    return atoms.get_chemical_formula()


def get_data():
    """Generate features from atoms objects."""
    # Connect database generated by a GA search.
    gadb = DataConnection('{}/data/gadb.db'.format(wkdir))

    # Get all relaxed candidates from the db file.
    print('Getting candidates from the database')
    all_cand = gadb.get_all_relaxed_candidates(use_extinct=False)

    # Setup the test and training datasets.
    testset = get_unique(atoms=all_cand, size=test_size, key='raw_score')

    trainset = get_train(atoms=all_cand, size=train_size,
                         taken=testset['taken'], key='raw_score')

    # Clear out some old saved data.
    for i in trainset['atoms']:
        del i.info['data']['nnmat']

    # Initiate the fingerprint generators with relevant input variables.
    print('Getting the fingerprints')
    pfpv = ParticleFingerprintGenerator(atom_numbers=[78, 79], max_bonds=13,
                                        get_nl=False, dx=0.2, cell_size=30.,
                                        nbin=4)

    train_features = return_fpv(trainset['atoms'], [pfpv.nearestneighbour_fpv])
    test_features = return_fpv(testset['atoms'], [pfpv.nearestneighbour_fpv])

    train_targets = []
    for a in trainset['atoms']:
        train_targets.append(a.info['key_value_pairs']['raw_score'])
    test_targets = []
    for a in testset['atoms']:
        test_targets.append(a.info['key_value_pairs']['raw_score'])

    return train_features, train_targets, trainset['atoms'], test_features, \
        test_targets, testset['atoms']


def gp_test(train_features, train_targets, train_atoms, test_features,
            test_targets, test_atoms):
    """Test acquisition functions."""
    # Test prediction routine with gaussian kernel.
    kdict = {'k1': {'type': 'gaussian', 'width': 1., 'scaling': 1.}}
    gp = GaussianProcess(train_fp=train_features, train_target=train_targets,
                         kernel_dict=kdict, regularization=1e-3,
                         optimize_hyperparameters=True, scale_data=True)
    pred = gp.predict(test_fp=test_features,
                      test_target=test_targets,
                      get_validation_error=True,
                      get_training_error=True,
                      uncertainty=True)

    print('gaussian prediction (rmse):',
          pred['validation_error']['rmse_average'])

    af = AcquisitionFunctions()
    acq = af.rank(targets=train_targets, predictions=pred['prediction'],
        uncertainty=pred['uncertainty'], train_features=train_features,
        test_features=test_features, metrics=['cdf', 'optimistic',
        'gaussian','UCB','EI','PI'])
    assert len(acq['cdf']) == len(pred['prediction'])
    assert len(acq['optimistic']) == len(pred['prediction'])
    assert len(acq['gaussian']) == len(pred['prediction'])
    assert len(acq['UCB']) == len(pred['prediction'])
    assert len(acq['EI']) == len(pred['prediction'])
    assert len(acq['PI']) == len(pred['prediction'])

    # acq = af.classify(classifier, train_atoms, test_atoms,
    #                   metrics=['cdf', 'optimistic', 'gaussian'])
    # assert len(acq['cdf']) == len(pred['prediction'])
    # assert len(acq['optimistic']) == len(pred['prediction'])
    # assert len(acq['gaussian']) == len(pred['prediction'])

if __name__ == '__main__':
    from pyinstrument import Profiler

    profiler = Profiler()
    profiler.start()

    train_features, train_targets, train_atoms, test_features, test_targets, \
        test_atoms = get_data()
    gp_test(train_features, train_targets, train_atoms,
            test_features, test_targets, test_atoms)

    profiler.stop()

    print(profiler.output_text(unicode=True, color=True))
