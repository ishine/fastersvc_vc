import torch
import torch.nn as nn
import torch.nn.functional as F

from .common import ResBlock, spectrogram


class ContentEncoder(nn.Module):
    def __init__(self,
                 n_fft=1920,
                 hop_size=480,
                 internal_channels=256,
                 kernel_size=7,
                 dilations=[1, 3, 9, 1],
                 output_channels=32,
                 ):
        super().__init__()
        self.n_fft = n_fft
        self.hop_size = hop_size

        self.input_layer = nn.Sequential(
            nn.Conv1d(n_fft // 2 + 1, 80, 1, bias=False),
            nn.Conv1d(80, internal_channels, 1, bias=False))

        self.res_stack = nn.Sequential(
                *[ResBlock(internal_channels, kernel_size, dilation=d, norm=True) for d in dilations])

        self.output_layer = nn.Conv1d(internal_channels, output_channels, 1)

    def forward(self, spec):
        x = self.input_layer(spec)
        x = self.res_stack(x)
        x = self.output_layer(x)
        return x

    def encode(self, wave):
        spec = spectrogram(wave, self.n_fft, self.hop_size)
        x = self.forward(spec)
        return x