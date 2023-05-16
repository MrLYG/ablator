import copy
import io
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import torch
from torch import nn

from torch.cuda.amp import GradScaler
from ablator import (
    ModelConfig,
    ModelWrapper,
    OptimizerConfig,
    RunConfig,
    TrainConfig,
    Derived,
)
import numpy as np

optimizer_config = OptimizerConfig(name="sgd", arguments={"lr": 0.1})
train_config = TrainConfig(
    dataset="test",
    batch_size=128,
    epochs=2,
    optimizer_config=optimizer_config,
    scheduler_config=None,
)

config = RunConfig(
    train_config=train_config,
    model_config=ModelConfig(),
    verbose="silent",
    device="cpu",
    amp=False,
)


amp_config = RunConfig(
    train_config=train_config,
    model_config=ModelConfig(),
    verbose="silent",
    device="cuda",
    amp=True,
)


class BadMyModel(nn.Module):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__()
        self.param = nn.Parameter(torch.ones(100))

    def forward(self, x: torch.Tensor):
        x = self.param + torch.rand_like(self.param) * 0.01
        return x.sum().abs()


class MyModel(nn.Module):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__()
        self.param = nn.Parameter(torch.ones(100))

    def forward(self, x: torch.Tensor):
        x = self.param + torch.rand_like(self.param) * 0.01
        return {"preds": x}, x.sum().abs()


class MyUnstableModel(nn.Module):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__()
        self.param = nn.Parameter(torch.ones(100))
        self.iteration = 0

    def forward(self, x: torch.Tensor):
        x = self.param + torch.rand_like(self.param) * 0.01
        self.iteration += 1
        if self.iteration > 10:
            return {"preds": x}, x.sum().abs() + torch.tensor(float("inf"))

        return {"preds": x}, x.sum().abs()


class MyWrongCustomModel(nn.Module):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__()
        self.param = nn.Parameter(torch.ones(100))
        self.iteration = 0

    def forward(self, x: torch.Tensor):
        x = self.param + torch.rand_like(self.param) * 0.01
        self.iteration += 1
        if self.iteration > 10:
            return {"preds": x}, None
        return {"preds": x}, x.sum().abs() * 1e-7


class MyCustomModel(nn.Module):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__()
        self.param = nn.Parameter(torch.ones(100))
        self.iteration = 0

    def forward(self, x: torch.Tensor):
        x = self.param + torch.rand_like(self.param) * 0.01
        self.iteration += 1
        if self.iteration > 10:
            if self.training:
                x.sum().abs().backward()
            return {"preds": x}, None

        return {"preds": x}, x.sum().abs() * 1e-7


class TestWrapper(ModelWrapper):
    def make_dataloader_train(self, run_config: RunConfig):
        dl = [torch.rand(100) for i in range(100)]
        return dl

    def make_dataloader_val(self, run_config: RunConfig):
        dl = [torch.rand(100) for i in range(100)]
        return dl


class DisambigiousTestWrapper(ModelWrapper):
    def make_dataloader_train(self, run_config: RunConfig):
        dl = [torch.rand(100) for i in range(100)]
        return dl

    def make_dataloader_val(self, run_config: RunConfig):
        dl = [torch.rand(100) for i in range(100)]
        return dl

    def config_parser(self, run_config: RunConfig):
        run_config.model_config.ambigious_var = 10
        return run_config


def assert_error_msg(fn, error_msg):
    try:
        fn()
        assert False, "Should have raised an error."
    except Exception as excp:
        if not error_msg == str(excp):
            raise excp


def test_error_models():
    assert_error_msg(
        lambda: TestWrapper(BadMyModel).train(config),
        "Model should return outputs: dict[str, torch.Tensor] | None, loss: torch.Tensor | None.",
    )
    assert_error_msg(
        lambda: TestWrapper(MyUnstableModel).train(config),
        "Loss Diverged. Terminating. loss: inf",
    )
    # TODO find how to address the model not doing backward
    # assert_error_msg(
    #     lambda: TestWrapper(MyWrongCustomModel).train(amp_config),
    #     "No inf checks were recorded for this optimizer.",
    # )


def assert_console_output(fn, assert_fn):
    f = io.StringIO()
    with redirect_stdout(f):
        fn()
    s = f.getvalue()
    assert assert_fn(s)


def capture_output(fn):
    out = io.StringIO()

    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        fn()

    return out.getvalue(), err.getvalue()


def test_verbosity():
    verbose_config = RunConfig(
        train_config=train_config,
        model_config=ModelConfig(),
        verbose="tqdm",
        metrics_n_batches=100,
    )
    out, err = capture_output(
        lambda: TestWrapper(MyCustomModel).train(verbose_config, debug=True)
    )

    assert err.strip().startswith("0%|          | 0/100") and len(out) == 0
    verbose_config = RunConfig(
        train_config=train_config,
        model_config=ModelConfig(),
        verbose="tqdm",
        metrics_n_batches=32,
    )
    out, err = capture_output(
        lambda: TestWrapper(MyCustomModel).train(verbose_config, debug=True)
    )
    assert (
        "Metrics batch-limit 32 is smaller than the validation dataloader length 100."
        in out
    )
    console_config = RunConfig(
        train_config=train_config, model_config=ModelConfig(), verbose="console"
    )
    out, err = capture_output(
        lambda: TestWrapper(MyCustomModel).train(console_config, debug=True)
    )
    assert len(err) == 0 and out.endswith("learning_rate: 0.1 total_steps: 200\n")


def test_train_stats():
    m = TestWrapper(MyCustomModel).train(config)
    res = m.to_dict()
    assert res["train_loss"] < 2e-05
    del res["train_loss"]

    assert res == {
        "val_loss": np.nan,
        "best_iteration": 0,
        "best_loss": float("inf"),
        "current_epoch": 2,
        "current_iteration": 200,
        "epochs": 2,
        "learning_rate": 0.1,
        "total_steps": 200,
    }


def test_state():
    wrapper = TestWrapper(MyCustomModel)
    assert_error_msg(
        lambda: wrapper.train_stats,
        "Undefined train_dataloader.",
    )
    assert wrapper.current_state == {}

    class AmbigiousModelConfig(ModelConfig):
        ambigious_var: Derived[int]

    _config = RunConfig(
        train_config=train_config,
        model_config=AmbigiousModelConfig(),
        verbose="silent",
        device="cpu",
        amp=False,
        random_seed=100,
    )

    assert_error_msg(
        lambda: wrapper._init_state(run_config=_config),
        "Ambigious configuration. Must provide value for ambigious_var",
    )
    disambigious_wrapper = DisambigiousTestWrapper(MyCustomModel)
    disambigious_wrapper._init_state(run_config=_config)

    _config = copy.deepcopy(config)
    _config.random_seed = 100
    wrapper = TestWrapper(MyCustomModel)
    wrapper._init_state(run_config=_config)

    assert len(wrapper.train_dataloader) == 100 and len(wrapper.val_dataloader) == 100
    train_stats = {
        "learning_rate": float("inf"),
        "total_steps": 200,
        "epochs": 2,
        "current_epoch": 0,
        "current_iteration": 0,
        "best_iteration": 0,
        "best_loss": float("inf"),
    }
    assert dict(wrapper.train_stats) == train_stats
    assert wrapper.current_state[
        "run_config"
    ] == _config.to_dict() and wrapper.current_state["metrics"] == {
        **train_stats,
        **{"train_loss": np.nan, "val_loss": np.nan},
    }
    assert str(wrapper.model.param.device) == "cpu"
    assert wrapper.model.param.requires_grad == True
    assert wrapper.current_checkpoint is None
    assert wrapper.best_loss == float("inf")
    assert isinstance(wrapper.model, MyCustomModel)
    assert isinstance(wrapper.scaler, GradScaler)
    assert wrapper.scheduler is None
    assert wrapper.logger is not None
    assert wrapper.device == "cpu"
    assert wrapper.amp == False
    assert wrapper.random_seed == 100


if __name__ == "__main__":
    # import shutil
    # tmp_path = Path("/tmp/")
    # shutil.rmtree(tmp_path.joinpath("test_exp"), ignore_errors=True)
    # test_load_save(tmp_path)
    test_error_models()
    # test_train_stats()
    # test_state()
    test_verbosity()
