from ablator.modules.metrics.main import TrainMetrics
from ablator.modules.metrics.stores import PredictionStore
import numpy as np
import math
import sys


moving_average_limit = 100
memory_limit = 100


def test_metrics(assert_error_msg):
    error_init = [
        (
            lambda: TrainMetrics(
                batch_limit=30,
                memory_limit=None,
                evaluation_functions={"mean": lambda x: np.mean(x)},
                moving_average_limit=moving_average_limit,
                tags=["my_tag"],
                static_aux_metrics={"some": float("inf")},
                moving_aux_metrics={"mean"},
            ),
            "Duplicate metric names with built-ins {'my_tag_mean'}",
        ),
        (
            lambda: TrainMetrics(
                batch_limit=30,
                memory_limit=None,
                evaluation_functions={"some": lambda x: np.mean(x)},
                moving_average_limit=moving_average_limit,
                tags=["my_tag"],
                static_aux_metrics={"my_tag_some": float("inf")},
                moving_aux_metrics={"mean"},
            ),
            "Duplicate metric names with built-ins {'my_tag_some'}",
        ),
        (
            lambda: TrainMetrics(
                batch_limit=30,
                memory_limit=None,
                evaluation_functions={"some": lambda x: np.mean(x)},
                moving_average_limit=moving_average_limit,
                tags=["my_tag"],
                static_aux_metrics={"my_tag_mean": float("inf")},
                moving_aux_metrics={"mean"},
            ),
            "Duplicate metric names with built-ins {'my_tag_mean'}",
        ),
    ]
    for error_obj, error_msg in error_init:
        assert_error_msg(error_obj, error_msg)

    m = TrainMetrics(
        batch_limit=30,
        memory_limit=None,
        evaluation_functions={"mean": lambda x: np.mean(x)},
        moving_average_limit=moving_average_limit,
        tags=["my_tag"],
        static_aux_metrics={"some": float("inf")},
        moving_aux_metrics={"ma_some"},
    )
    assert m.to_dict() == {
        "my_tag_mean": np.nan,
        "my_tag_ma_some": np.nan,
        "some": float("inf"),
    }
    assert_error_msg(
        lambda: m.update_ma_metrics({"ma_some": 0.1, "ma_some_2": 2}, tag="my_tag"),
        "There are difference in the class metrics: ['my_tag_ma_some'] and parsed metrics ['my_tag_ma_some', 'my_tag_ma_some_2']",
    )
    assert_error_msg(
        lambda: m.update_ma_metrics({"a": 0.1}, tag="my_tag"),
        "There are difference in the class metrics: ['my_tag_ma_some'] and parsed metrics ['my_tag_a']",
    )
    assert_error_msg(
        lambda: m.update_static_metrics({"some_2": 1}),
        "There are difference in the class metrics: ['some'] and updated metrics ['some_2']",
    )
    assert_error_msg(
        lambda: m.update_ma_metrics({"ma_some": ""}, tag="my_tag"),
        "Invalid MovingAverage value type <class 'str'>",
    )
    m.update_static_metrics({"some": ""})
    assert m.to_dict() == {"my_tag_ma_some": np.nan, "my_tag_mean": np.nan, "some": ""}

    m.update_ma_metrics({"ma_some": np.array([0])}, tag="my_tag")
    assert m.to_dict() == {"my_tag_ma_some": 0.0, "my_tag_mean": np.nan, "some": ""}

    for i in np.arange(moving_average_limit + 10):
        m.update_ma_metrics({"ma_some": int(i)}, tag="my_tag")
    assert m.to_dict() == {
        "my_tag_ma_some": np.mean(np.arange(10, moving_average_limit + 10)),
        "my_tag_mean": np.nan,
        "some": "",
    }

    m = TrainMetrics(
        batch_limit=30,
        memory_limit=memory_limit,
        evaluation_functions={"mean": lambda labels, preds: "a"},
        moving_average_limit=100,
        tags=["my_tag"],
        static_aux_metrics={"some": 0},
        moving_aux_metrics={"ma_some"},
    )
    for i in range(1000):
        m.update_ma_metrics({"ma_some": int(i)}, tag="my_tag")

    assert sys.getsizeof(m._get_ma("my_tag_ma_some").arr) < memory_limit
    assert m.to_dict() == {"my_tag_ma_some": 997.5, "my_tag_mean": np.nan, "some": 0}

    assert_error_msg(
        lambda: m.append_batch(1, preds="", labels=None, tag=""),
        "Metrics.append_batch takes no positional arguments.",
    )
    assert_error_msg(
        lambda: m.append_batch(preds="", labels="", tag=""),
        "Undefined tag ''. Metric tags ['my_tag']",
    )
    assert_error_msg(
        lambda: [
            m.append_batch(preds=np.array([""]), labels=np.array([""]), tag="my_tag"),
            m.evaluate("my_tag"),
        ],
        "Invalid value a returned by evaluation function <lambda>. Must be numeric scalar.",
    )
    assert_error_msg(
        lambda: [
            m.append_batch(preds=np.array([""]), labels=np.array([""]), tag="my_tag"),
            m.append_batch(preds=np.array([""]), tag="my_tag"),
        ],
        "Missing keys from the prediction store update. Expected: ['labels', 'preds'], received ['preds']",
    )
    assert_error_msg(
        lambda: [
            m.append_batch(preds=np.array([""]), labels=np.array([""]), tag="my_tag"),
            m.append_batch(
                preds=np.array([""]), labels=np.array([""] * 2), tag="my_tag"
            ),
        ],
        "Different number of batches between inputs. Sizes: {'preds': 1, 'labels': 2}",
    )
    m2 = TrainMetrics(
        batch_limit=30,
        memory_limit=memory_limit,
        evaluation_functions={"mean": lambda somex: np.mean(somex)},
        moving_average_limit=100,
        tags=["my_tag"],
        static_aux_metrics={"some": 0},
        moving_aux_metrics={"ma_some"},
    )
    assert_error_msg(
        lambda: [
            m2.append_batch(
                somex=np.array([100]), labels=np.array([1000]), tag="my_tag"
            ),
            m2.evaluate("my_tag"),
        ],
        "Evaluation function arguments ['somex'] different than stored predictions: ['labels', 'somex']",
    )
    m3 = TrainMetrics(
        batch_limit=30,
        memory_limit=None,
        evaluation_functions={"mean": lambda somex: np.mean(somex)},
        moving_average_limit=100,
        tags=["my_tag"],
    )
    assert m3.evaluate("my_tag") == {}, f"Expected None when there are no predictions to evaluate"
    m3.append_batch(somex=np.array([100]), tag="my_tag")
    m3.evaluate("my_tag", reset=False, update_ma=True)
    m3.append_batch(somex=np.array([0] * 3), tag="my_tag")

    m3.evaluate("my_tag", reset=False, update_ma=False)
    assert m3.to_dict() == {"my_tag_mean": 100.0}
    m3.evaluate("my_tag", reset=False, update_ma=True)
    assert m3.to_dict() == {"my_tag_mean": 62.5}
    m3.append_batch(somex=np.array([0] * 3), tag="my_tag")
    assert m3.to_dict() == {"my_tag_mean": 62.5}
    m3.evaluate("my_tag", reset=False, update_ma=True)
    assert np.isclose(m3.to_dict()["my_tag_mean"], 46.42857142857142)

    # Test if reset function works
    m3.reset(tag="my_tag")
    m3.evaluate("my_tag", reset=False, update_ma=True)
    value = m3.to_dict()["my_tag_mean"]
    assert math.isnan(value)

    # Test if TrainMetrics with auto add `train` tag when tags is None.
    m4 = TrainMetrics(
        batch_limit=30,
        memory_limit=None,
        evaluation_functions={"mean": lambda x: np.mean(x)},
        moving_average_limit=100,
        tags=None,
        static_aux_metrics={"lr": 1.0},
        moving_aux_metrics={"loss"},
    )
    value = m4.to_dict()["train_mean"]
    assert math.isnan(value)


def test_prediction_store_reset(assert_error_msg):
    ps = PredictionStore(batch_limit=30, memory_limit=100, moving_average_limit=3000,
                         evaluation_functions={"mean": lambda preds, labels: np.mean(preds) + np.mean(labels)})

    # Test evaluate when no predictions have been appended.
    res = ps.evaluate()
    assert res == {}, "Evaluate should return an empty dict when no predictions have been appended."

    # Test the reset function when no predictions have been appended.
    try:
        ps.reset()
    except Exception:
        assert False, "Reset should not raise an exception when no predictions have been appended."

    # Add some predictions.
    ps.append(preds=np.array([1, 2, 3]), labels=np.array([1, 1, 1]))

    # Test evaluate when predictions have been appended.
    res = ps.evaluate()
    assert res == {"mean": 3.0}, "Evaluate should return the correct evaluation when predictions have been appended."

    # Test that the reset function clears the appended predictions.
    ps.reset()
    assert len(ps._get_arr('preds')) == 0, "Reset did not clear the appended predictions."
    assert len(ps._get_arr('labels')) == 0, "Reset did not clear the appended predictions."


if __name__ == "__main__":

    def assert_error_msg(fn, error_msg):
        try:
            fn()
            assert False
        except Exception as excp:
            if not error_msg == str(excp):
                raise excp

    test_metrics(assert_error_msg)
    test_prediction_store_reset(assert_error_msg)
