"""Tests for autoencoder model and trainer."""

import numpy as np
import pytest
import torch

from src.state.autoencoder import (
    AutoencoderConfig,
    Conv1DAutoencoder,
    AutoencoderTrainer,
    TrainerConfig,
)


class TestConv1DAutoencoder:
    """Tests for Conv1DAutoencoder."""

    @pytest.fixture
    def config(self) -> AutoencoderConfig:
        return AutoencoderConfig(
            input_size=10,
            window_size=20,
            latent_dim=4,
            encoder_channels=[16, 32],
        )

    @pytest.fixture
    def model(self, config: AutoencoderConfig) -> Conv1DAutoencoder:
        return Conv1DAutoencoder(config)

    def test_init(self, model: Conv1DAutoencoder):
        """Test model initialization."""
        assert model.config.latent_dim == 4
        assert model.config.input_size == 10

    def test_encode_shape(self, model: Conv1DAutoencoder):
        """Test encoder output shape."""
        x = torch.randn(8, 20, 10)  # batch, window, features
        z = model.encode(x)
        
        assert z.shape == (8, 4)  # batch, latent_dim

    def test_decode_shape(self, model: Conv1DAutoencoder):
        """Test decoder output shape."""
        z = torch.randn(8, 4)
        x_hat = model.decode(z)
        
        assert x_hat.shape == (8, 20, 10)  # batch, window, features

    def test_forward_shape(self, model: Conv1DAutoencoder):
        """Test full forward pass shape."""
        x = torch.randn(8, 20, 10)
        x_hat = model(x)
        
        assert x_hat.shape == x.shape

    def test_gradient_flow(self, model: Conv1DAutoencoder):
        """Test gradients flow through model."""
        x = torch.randn(4, 20, 10, requires_grad=True)
        x_hat = model(x)
        loss = torch.nn.functional.mse_loss(x_hat, x)
        loss.backward()
        
        # Check gradients exist
        for param in model.parameters():
            assert param.grad is not None


class TestAutoencoderTrainer:
    """Tests for AutoencoderTrainer."""

    @pytest.fixture
    def trainer(self) -> AutoencoderTrainer:
        config = AutoencoderConfig(
            input_size=10,
            window_size=20,
            latent_dim=4,
            encoder_channels=[8, 16],
        )
        model = Conv1DAutoencoder(config)
        trainer_config = TrainerConfig(
            epochs=2,
            batch_size=8,
            validation_split=0.2,
        )
        return AutoencoderTrainer(model, trainer_config)

    def test_fit(self, trainer: AutoencoderTrainer, sample_windows: np.ndarray):
        """Test training loop runs."""
        history = trainer.fit(sample_windows)
        
        assert "train_loss" in history
        assert "val_loss" in history
        assert len(history["train_loss"]) > 0

    def test_encode(self, trainer: AutoencoderTrainer, sample_windows: np.ndarray):
        """Test encoding after training."""
        trainer.fit(sample_windows)
        states = trainer.encode(sample_windows[:10])
        
        assert states.shape == (10, 4)

    def test_reconstruct(self, trainer: AutoencoderTrainer, sample_windows: np.ndarray):
        """Test reconstruction after training."""
        trainer.fit(sample_windows)
        reconstructed = trainer.reconstruct(sample_windows[:10])
        
        assert reconstructed.shape == sample_windows[:10].shape

    def test_callback(self, trainer: AutoencoderTrainer, sample_windows: np.ndarray):
        """Test callback is called during training."""
        epochs_seen = []
        
        def callback(epoch, train_loss, val_loss):
            epochs_seen.append(epoch)
        
        trainer.fit(sample_windows, callback=callback)
        
        assert len(epochs_seen) > 0
