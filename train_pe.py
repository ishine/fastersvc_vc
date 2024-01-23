import argparse
import os 

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import torchaudio

from tqdm import tqdm

from module.dataset import WaveFileDirectoryWithF0
from module.pitch_estimator import PitchEstimator

parser = argparse.ArgumentParser(description="train pitch estimation")

parser.add_argument('dataset')
parser.add_argument('-pep', '--pitch_estimator_path', default='models/pitch_estimator.pt')
parser.add_argument('-lr', '--learning-rate', type=float, default=1e-4)
parser.add_argument('-d', '--device', default='cuda')
parser.add_argument('-e', '--epoch', default=1000, type=int)
parser.add_argument('-b', '--batch-size', default=16, type=int)
parser.add_argument('-len', '--length', default=122880, type=int)
parser.add_argument('-m', '--max-data', default=-1, type=int)
parser.add_argument('-fp16', default=False, type=bool)

args = parser.parse_args()


def load_or_init_models(device=torch.device('cpu')):
    pe = PitchEstimator().to(device)
    if os.path.exists(args.pitch_estimator_path):
        pe.load_state_dict(torch.load(args.pitch_estimator_path, map_location=device))
    return pe

def save_models(pe):
    print("Saving models...")
    torch.save(pe.state_dict(), args.pitch_estimator_path)
    print("Complete!")


device = torch.device(args.device)
PE = load_or_init_models(device)

ds = WaveFileDirectoryWithF0(
        [args.dataset],
        length=args.length,
        max_files=args.max_data
        )

dl = torch.utils.data.DataLoader(ds, batch_size=args.batch_size, shuffle=True)

scaler = torch.cuda.amp.GradScaler(enabled=args.fp16)

Opt = optim.AdamW(PE.parameters(), lr=args.learning_rate)

CrossEntropy = nn.CrossEntropyLoss(ignore_index=0).to(device)

# Training
step_count = 0

for epoch in range(args.epoch):
    tqdm.write(f"Epoch #{epoch}")
    bar = tqdm(total=len(ds))
    for batch, (wave, f0) in enumerate(dl):
        wave = wave.to(device)
        gain = torch.rand(wave.shape[0], 1, device=device) * 0.05
        noise = torch.randn_like(wave)
        wave = wave + noise * gain
        N = wave.shape[0]
        f0 = f0.to(device)

        Opt.zero_grad()
        with torch.cuda.amp.autocast(enabled=args.fp16):
            logits = PE.logits(wave)
            label = PE.freq2id(f0.squeeze(1))
            loss = CrossEntropy(logits, label)

        scaler.scale(loss).backward()
        scaler.step(Opt)

        scaler.update()

        step_count += 1

        tqdm.write(f"Step {step_count}, loss: {loss.item()}")

        bar.update(N)

        if batch % 1000 == 0:
            save_models(PE)

print("Training Complete!")
save_models(PE)