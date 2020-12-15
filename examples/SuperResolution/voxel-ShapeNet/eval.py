import argparse
import os
import torch
import sys
from tqdm import tqdm

from torch.utils.data import DataLoader

from architectures import EncoderDecoder_32_128, EncoderDecoderForNLL_32_128
from utils import up_sample
import kaolin as kal


parser = argparse.ArgumentParser()
parser.add_argument('--shapenet-root', type=str, required=True, help='Root directory of the ShapeNet dataset.')
parser.add_argument('--cache-dir', type=str, default='cache', help='Directory where intermediate representations will be stored.')
parser.add_argument('--expid', type=str, default='superres', help='Unique experiment identifier.')
parser.add_argument('--device', type=str, default='cuda', help='Device to use.')
parser.add_argument('--categories', type=str, nargs='+', default=['chair'], help='list of object classes to use.')
parser.add_argument('--no-vis', action='store_true', help='Disable visualization of each model while evaluating.')
parser.add_argument('--batchsize', type=int, default=16, help='Batch size.')
args = parser.parse_args()


device = torch.device(args.device)

# Dataset Setup
valid_set = kal.datasets.ShapeNet_Voxels(root=args.shapenet_root, cache_dir=args.cache_dir,
                                         categories=args.categories, train=False, resolutions=[128, 32],
                                         split=.97)
dataloader_val = DataLoader(valid_set, batch_size=args.batchsize, shuffle=False, num_workers=8)


# Model
model = EncoderDecoderForNLL_32_128()
model = model.to(device)

# Load saved weights
model.load_state_dict(torch.load(f'log/{args.expid}/best.pth'))

iou_epoch = 0.
iou_NN_epoch = 0.
num_batches = 0


model.eval()
with torch.no_grad():
    for sample in tqdm(dataloader_val):
        data = sample['data']
        tgt = data['128'].to(device)
        inp = data['32'].to(device)

        # inference
        pred = model(inp.unsqueeze(1))[:, 1, :, :]

        iou = kal.metrics.voxel.iou(pred.contiguous(), tgt)
        iou_epoch += iou

        NN_pred = up_sample(inp)
        iou_NN = kal.metrics.voxel.iou(NN_pred.contiguous(), tgt)
        iou_NN_epoch += iou_NN

        if not args.no_vis:
            for i in range(inp.shape[0]):
                print('Rendering low resolution input')
                kal.visualize.show_voxelgrid(inp[i], mode='exact', thresh=.5)
                print('Rendering high resolution target')
                kal.visualize.show_voxelgrid(tgt[i], mode='exact', thresh=.5)
                print('Rendering high resolution prediction')
                kal.visualize.show_voxelgrid(pred[i], mode='exact', thresh=.5)
                print('----------------------')
        num_batches += 1.
out_iou_NN = iou_NN_epoch / float(num_batches)
print('Nearest Neighbor Baseline IoU over validation set is {0}'.format(out_iou_NN))
out_iou = iou_epoch.item() / float(num_batches)
print('IoU over validation set is {0}'.format(out_iou))
