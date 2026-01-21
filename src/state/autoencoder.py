"""PyTorch autoencoder for nonlinear state representation."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset


@dataclass
class AutoencoderConfig:
    """Configuration for autoencoder architecture.

    Attributes:
        input_size: Number of features per time step
        window_size: Length of temporal window
        latent_dim: Dimension of latent state (default 8)
        encoder_channels: List of channel sizes for encoder conv layers
        kernel_size: Kernel size for conv layers
        dropout: Dropout rate
    """

    input_size: int = 15
    window_size: int = 60
    latent_dim: int = 8
    encoder_channels: list[int] = field(default_factory=lambda: [32, 64, 128])
    kernel_size: int = 3
    dropout: float = 0.1


class Conv1DEncoder(nn.Module):
    """1D Convolutional encoder for temporal windows."""

    def __init__(self, config: AutoencoderConfig):
        super().__init__()
        self.config = config

        layers = []
        in_channels = config.input_size

        for out_channels in config.encoder_channels:
            layers.extend(
                [
                    nn.Conv1d(
                        in_channels,
                        out_channels,
                        kernel_size=config.kernel_size,
                        padding=config.kernel_size // 2,
                    ),
                    nn.BatchNorm1d(out_channels),
                    nn.ReLU(),
                    nn.Dropout(config.dropout),
                ]
            )
            in_channels = out_channels

        self.conv_layers = nn.Sequential(*layers)

        # Global average pooling followed by linear to latent
        self.fc = nn.Linear(config.encoder_channels[-1], config.latent_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass.

        Args:
            x: Input tensor of shape (batch, window_size, n_features)

        Returns:
            Latent representation of shape (batch, latent_dim)
        """
        # Conv1d expects (batch, channels, length)
        x = x.transpose(1, 2)
        x = self.conv_layers(x)
        # Global average pooling
        x = x.mean(dim=2)
        x = self.fc(x)
        return x


class Conv1DDecoder(nn.Module):
    """1D Convolutional decoder for temporal windows."""

    def __init__(self, config: AutoencoderConfig):
        super().__init__()
        self.config = config

        # Project latent to initial feature map
        self.fc = nn.Linear(
            config.latent_dim, config.encoder_channels[-1] * config.window_size
        )

        layers = []
        channels = list(reversed(config.encoder_channels))

        for i, out_channels in enumerate(channels[1:]):
            layers.extend(
                [
                    nn.ConvTranspose1d(
                        channels[i],
                        out_channels,
                        kernel_size=config.kernel_size,
                        padding=config.kernel_size // 2,
                    ),
                    nn.BatchNorm1d(out_channels),
                    nn.ReLU(),
                    nn.Dropout(config.dropout),
                ]
            )

        # Final layer to reconstruct input
        layers.append(
            nn.ConvTranspose1d(
                channels[-1],
                config.input_size,
                kernel_size=config.kernel_size,
                padding=config.kernel_size // 2,
            )
        )

        self.conv_layers = nn.Sequential(*layers)

    def forward(self, z: torch.Tensor) -> torch.Tensor:
        """Forward pass.

        Args:
            z: Latent tensor of shape (batch, latent_dim)

        Returns:
            Reconstructed tensor of shape (batch, window_size, n_features)
        """
        batch_size = z.shape[0]
        x = self.fc(z)
        x = x.view(batch_size, self.config.encoder_channels[-1], self.config.window_size)
        x = self.conv_layers(x)
        # Transpose back to (batch, window_size, n_features)
        x = x.transpose(1, 2)
        return x


class Conv1DAutoencoder(nn.Module):
    """Complete 1D Convolutional Autoencoder for state learning.

    Architecture:
    - Conv1D encoder with batch norm and dropout
    - Bottleneck layer producing latent state
    - Conv1D decoder reconstructing input

    Example:
        >>> config = AutoencoderConfig(input_size=15, window_size=60, latent_dim=8)
        >>> model = Conv1DAutoencoder(config)
        >>> x = torch.randn(32, 60, 15)  # batch of windows
        >>> z = model.encode(x)  # (32, 8)
        >>> x_hat = model(x)  # (32, 60, 15)
    """

    def __init__(self, config: AutoencoderConfig):
        super().__init__()
        self.config = config
        self.encoder = Conv1DEncoder(config)
        self.decoder = Conv1DDecoder(config)

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        """Encode input to latent representation."""
        return self.encoder(x)

    def decode(self, z: torch.Tensor) -> torch.Tensor:
        """Decode latent representation to reconstruction."""
        return self.decoder(z)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Full forward pass (encode + decode)."""
        z = self.encode(x)
        return self.decode(z)


@dataclass
class TrainerConfig:
    """Configuration for autoencoder training.

    Attributes:
        learning_rate: Initial learning rate
        batch_size: Training batch size
        epochs: Maximum number of epochs
        patience: Early stopping patience
        lr_scheduler_factor: LR reduction factor on plateau
        lr_scheduler_patience: LR scheduler patience
        validation_split: Fraction of data for validation
        device: Device to train on (cuda/cpu/auto)
    """

    learning_rate: float = 1e-3
    batch_size: int = 64
    epochs: int = 100
    patience: int = 10
    lr_scheduler_factor: float = 0.5
    lr_scheduler_patience: int = 5
    validation_split: float = 0.1
    device: str = "auto"


class AutoencoderTrainer:
    """Trainer for Conv1D autoencoder.

    Handles:
    - Training loop with early stopping
    - Learning rate scheduling
    - Validation monitoring
    - Model saving/loading

    Example:
        >>> trainer = AutoencoderTrainer(model, learning_rate=1e-3)
        >>> history = trainer.fit(train_windows)
        >>> trainer.save("model.pt")
    """

    def __init__(
        self,
        model: Conv1DAutoencoder,
        config: TrainerConfig | None = None,
    ):
        """Initialize trainer.

        Args:
            model: Autoencoder model to train
            config: Training configuration
        """
        self.model = model
        self.config = config or TrainerConfig()

        # Set device
        if self.config.device == "auto":
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(self.config.device)

        self.model.to(self.device)

        # Setup optimizer and scheduler
        self.optimizer = torch.optim.Adam(
            self.model.parameters(), lr=self.config.learning_rate
        )
        self.scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            self.optimizer,
            mode="min",
            factor=self.config.lr_scheduler_factor,
            patience=self.config.lr_scheduler_patience,
        )
        self.criterion = nn.MSELoss()

        # Training state
        self.best_loss = float("inf")
        self.patience_counter = 0
        self.history: dict[str, list[float]] = {"train_loss": [], "val_loss": []}

    def _create_dataloaders(
        self, windows: np.ndarray
    ) -> tuple[DataLoader, DataLoader | None]:
        """Create train and validation dataloaders."""
        n_samples = len(windows)
        n_val = int(n_samples * self.config.validation_split)
        n_train = n_samples - n_val

        # Shuffle indices
        indices = np.random.permutation(n_samples)
        train_indices = indices[:n_train]
        val_indices = indices[n_train:]

        train_data = torch.tensor(windows[train_indices], dtype=torch.float32)
        train_dataset = TensorDataset(train_data)
        train_loader = DataLoader(
            train_dataset, batch_size=self.config.batch_size, shuffle=True
        )

        val_loader = None
        if n_val > 0:
            val_data = torch.tensor(windows[val_indices], dtype=torch.float32)
            val_dataset = TensorDataset(val_data)
            val_loader = DataLoader(
                val_dataset, batch_size=self.config.batch_size, shuffle=False
            )

        return train_loader, val_loader

    def _train_epoch(self, loader: DataLoader) -> float:
        """Train for one epoch."""
        self.model.train()
        total_loss = 0.0

        for (batch,) in loader:
            batch = batch.to(self.device)

            self.optimizer.zero_grad()
            output = self.model(batch)
            loss = self.criterion(output, batch)
            loss.backward()
            self.optimizer.step()

            total_loss += loss.item() * len(batch)

        return total_loss / len(loader.dataset)

    @torch.no_grad()
    def _validate(self, loader: DataLoader) -> float:
        """Validate on held-out data."""
        self.model.eval()
        total_loss = 0.0

        for (batch,) in loader:
            batch = batch.to(self.device)
            output = self.model(batch)
            loss = self.criterion(output, batch)
            total_loss += loss.item() * len(batch)

        return total_loss / len(loader.dataset)

    def fit(
        self,
        windows: np.ndarray,
        callback: Callable[[int, float, float], None] | None = None,
    ) -> dict[str, list[float]]:
        """Train the autoencoder.

        Args:
            windows: Training windows of shape (n_samples, window_size, n_features)
            callback: Optional callback(epoch, train_loss, val_loss)

        Returns:
            Training history dictionary
        """
        train_loader, val_loader = self._create_dataloaders(windows)

        for epoch in range(self.config.epochs):
            train_loss = self._train_epoch(train_loader)
            self.history["train_loss"].append(train_loss)

            val_loss = train_loss
            if val_loader is not None:
                val_loss = self._validate(val_loader)
            self.history["val_loss"].append(val_loss)

            # LR scheduling
            self.scheduler.step(val_loss)

            # Early stopping
            if val_loss < self.best_loss:
                self.best_loss = val_loss
                self.patience_counter = 0
            else:
                self.patience_counter += 1
                if self.patience_counter >= self.config.patience:
                    break

            if callback is not None:
                callback(epoch, train_loss, val_loss)

        return self.history

    @torch.no_grad()
    def encode(self, windows: np.ndarray) -> np.ndarray:
        """Encode windows to latent states.

        Args:
            windows: Windows of shape (n_samples, window_size, n_features)

        Returns:
            Latent states of shape (n_samples, latent_dim)
        """
        self.model.eval()
        tensor = torch.tensor(windows, dtype=torch.float32).to(self.device)
        states = self.model.encode(tensor)
        return states.cpu().numpy()

    @torch.no_grad()
    def reconstruct(self, windows: np.ndarray) -> np.ndarray:
        """Reconstruct windows through autoencoder.

        Args:
            windows: Windows of shape (n_samples, window_size, n_features)

        Returns:
            Reconstructed windows
        """
        self.model.eval()
        tensor = torch.tensor(windows, dtype=torch.float32).to(self.device)
        output = self.model(tensor)
        return output.cpu().numpy()

    def save(self, path: str | Path) -> None:
        """Save model and optimizer state.

        Args:
            path: Path to save checkpoint
        """
        torch.save(
            {
                "model_state_dict": self.model.state_dict(),
                "optimizer_state_dict": self.optimizer.state_dict(),
                "config": self.model.config,
                "trainer_config": self.config,
                "best_loss": self.best_loss,
                "history": self.history,
            },
            path,
        )

    def load(self, path: str | Path) -> None:
        """Load model from checkpoint.

        Args:
            path: Path to checkpoint
        """
        checkpoint = torch.load(path, map_location=self.device)
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        self.best_loss = checkpoint.get("best_loss", float("inf"))
        self.history = checkpoint.get("history", {"train_loss": [], "val_loss": []})
