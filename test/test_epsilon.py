import pyabc
import numpy as np
import pandas as pd
import pytest
import copy


def test_noepsilon():
    eps = pyabc.NoEpsilon()
    assert not np.isfinite(eps(42))


def test_constantepsilon():
    eps = pyabc.ConstantEpsilon(42)
    assert np.isclose(eps(100), 42)


def test_listepsilon():
    eps = pyabc.ListEpsilon([3.5, 2.3, 1, 0.3])
    with pytest.raises(Exception):
        eps(4)


def test_quantileepsilon():
    mpl = 1.1
    df = pd.DataFrame({
        'distance': [1, 2, 3, 4],
        'w': [2, 1, 1, 1]
    })

    eps = pyabc.QuantileEpsilon(
        initial_epsilon=5.1, alpha=0.5,
        quantile_multiplier=mpl, weighted=False)

    # check if initial value is respected
    eps.initialize(0, lambda: df, lambda: None, None, None)
    assert np.isclose(eps(0), 5.1)

    # check if quantile is computed correctly
    eps.update(1, lambda: df, lambda: None, None, None)
    assert np.isclose(eps(1), mpl * 2.5)

    # use other quantile
    eps = pyabc.QuantileEpsilon(alpha=0.9, weighted=True)
    eps.initialize(0, lambda: df, lambda: None, None, None)
    assert eps(0) >= 3 and eps(0) <= 4


def test_medianepsilon():
    # functionality already covered by quantile epsilon tests
    eps = pyabc.MedianEpsilon()
    assert np.isclose(eps.alpha, 0.5)


def test_temperature():
    weighted_distances = pd.DataFrame({
        'distance': [1, 2, 3, 4],
        'w': [2, 1, 1, 0]})
    all_records = [
        dict(distance=np.random.randn(),
             transition_pd_prev=np.random.randn(),
             transition_pd=np.random.randn(),
             accepted=True if np.random.random() > 0.5 else False)
        for _ in range(20)]
    acceptor_config = {
        'pdf_norm': 5,
        'kernel_scale': pyabc.distance.SCALE_LOG}
    nr_pop = 3
    eps = pyabc.Temperature(initial_temperature=42)
    eps.initialize(0, lambda: weighted_distances, lambda: all_records,
                   nr_pop, acceptor_config)

    # check if initial value is respected
    assert eps(0) == 42

    eps.update(1, lambda: weighted_distances, lambda: all_records,
               0.4, acceptor_config)
    assert eps(1) < 42

    # last time
    eps.update(2, lambda: weighted_distances, lambda: all_records,
               0.2, acceptor_config)
    assert eps(2) == 1


scheme_args = dict(
    get_weighted_distances=lambda: pd.DataFrame({
        'distance': [4, 5, 6, 1],
        'w': [0.25, 0.5, 0.10, 0.15]
    }),
    get_all_records=lambda: [
        dict(distance=np.random.randn(),
             transition_pd_prev=np.random.randn(),
             transition_pd=np.random.randn(),
             accepted=True if np.random.random() > 0.5 else False)
        for _ in range(20)],
    max_nr_populations=3,
    pdf_norm=10,
    kernel_scale=pyabc.distance.SCALE_LOG,
    prev_temperature=7.53,
    acceptance_rate=0.4)


def test_scheme_basic():
    schemes = [
        pyabc.AcceptanceRateScheme(),
        pyabc.ExponentialDecayScheme(),
        pyabc.PolynomialDecayScheme(),
        pyabc.DalyScheme(),
        pyabc.FrielPettittScheme(),
        pyabc.EssScheme()
    ]
    for scheme in schemes:
        # call them
        temp = scheme(t=0, **scheme_args)
        assert 1.0 < temp and temp < np.inf


def test_scheme_acceptancerate():
    scheme = pyabc.AcceptanceRateScheme()
    temp = scheme(t=0, **scheme_args)
    assert 1.0 < temp

    # high acceptance probabilities
    _scheme_args = copy.deepcopy(scheme_args)
    # change normalization s.t. most have 1.0 acceptance rate
    records = pd.DataFrame(_scheme_args['get_all_records']())
    _scheme_args['pdf_norm'] = min(records['distance'])
    temp = scheme(t=0, **_scheme_args)
    assert temp == 1.0


def test_scheme_exponentialdecay():
    scheme = pyabc.ExponentialDecayScheme()

    # check no base temperature
    _scheme_args = copy.deepcopy(scheme_args)
    _scheme_args['prev_temperature'] = None
    temp = scheme(t=0, **_scheme_args)
    assert temp == np.inf

    # check normal behavior
    temp = scheme(t=0, **scheme_args)
    assert 1.0 < temp and temp < np.inf
    temp = scheme(t=2, **scheme_args)
    assert temp == 1.0


def test_default_eps():
    def model(par):
        return {'s0': par['p0'] + np.random.random(),
                's1': np.random.random()}

    x_0 = {'s0': 0.4, 's1': 0.6}

    prior = pyabc.Distribution(p0=pyabc.RV('uniform', -1, 2))

    # usual setting
    abc = pyabc.ABCSMC(model, prior, population_size=10)
    abc.new(pyabc.create_sqlite_db_id(), x_0)
    abc.run(max_nr_populations=3)

    assert abc.minimum_epsilon == 0.0

    # noisy setting
    acceptor = pyabc.StochasticAcceptor()
    eps = pyabc.Temperature()

    distance = pyabc.IndependentNormalKernel(var=np.array([1, 1]))

    abc = pyabc.ABCSMC(model, prior, distance, eps=eps,
                       acceptor=acceptor, population_size=10)
    abc.new(pyabc.create_sqlite_db_id(), x_0)
    abc.run(max_nr_populations=3)

    assert abc.minimum_epsilon == 1.0
