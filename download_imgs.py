#!/usr/bin/env python

import argparse
import json
import os
import subprocess

import cv2
import numpy as np
from PIL import Image


DATA_FILE = "assets/data.json"
WRONG_COMMITS = ["Bus", "Boar", "Dromedary"]

SAP_WIKI_URL = {"Dirty Rat": "3/38/Dirty_Rat.png",
                "Tabby Cat": "b/b3/Tabby_Cat.png",
                "Zombie Cricket": "2/24/Zombie_Cricket.png",
                "Zombie Fly": "b/ba/Zombie_Fly.png",
                "Garlic Armor": "c/cc/Garlic.png", }


def download_from_wiki(img_name, dst_file, img_size):
    print(f"Processing {img_name} (from wiki to {dst_file})")
    revision = SAP_WIKI_URL[img_name]
    img_url = f"https://static.wikia.nocookie.net/superautopets/images/{revision}"
    download_cmd = ["wget", img_url, '-O', dst_file]
    subprocess.run(download_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    img = cv2.imread(dst_file, cv2.IMREAD_UNCHANGED)
    h, w, _ = img.shape
    if h > w:
        before_col = np.zeros((h, (h - w) // 2, 4), np.uint8)
        after_col = np.zeros((h, (h - w) // 2, 4), np.uint8)
        img = np.hstack((before_col, img, after_col))

    elif h < w:
        before_row = np.zeros(((w - h) // 2, w, 4), np.uint8)
        after_row = np.zeros(((w - h) // 2, w, 4), np.uint8)
        img = np.vstack((before_row, img, after_row))

    # BGR to RGB
    img = img[..., (2, 1, 0, 3)]

    if not dst_file.endswith('_alt.png'):
        h, w = img.shape[:2]
        mask = (img[:, :, 3] > 0).astype(np.uint8)

        tmp_mask = np.zeros((h+2, w+2), np.uint8)
        tmp_img = img.copy()[:, :, :3].astype(np.uint8)
        cv2.floodFill(tmp_img, tmp_mask, (1, 1), None, (50, 50, 50), (250, 250, 250), flags=cv2.FLOODFILL_MASK_ONLY)
        mask *= (1 - tmp_mask[1:-1, 1:-1])

        hls = cv2.cvtColor(img, cv2.COLOR_RGB2HLS)[..., 1]
        mask *= (0 < hls) * (hls < 230)

        tmp_mask = np.zeros((h+2, w+2), np.uint8)
        cv2.floodFill(mask, tmp_mask, (30, 40), None, flags=cv2.FLOODFILL_MASK_ONLY)
        mask *= (1 - tmp_mask[1:-1, 1:-1])

        # Keep the black eyes
        if "Zombie Cricket" in dst_file:
            mask[105:135, 55:75] = 1

        elif "Zombie Fly" in dst_file:
            mask[105:150, 60:105] = 1
            cv2.floodFill(mask, None, (50, 115), 1)

        img *= mask[..., np.newaxis]

    img = cv2.resize(img, (img_size, img_size))
    img = Image.fromarray(img)
    img.save(dst_file)

def download_img(data, path, img_size):
    source = data['image']['source']
    commit = data['image']['commit']
    code = data['image']['unicodeCodePoint']
    code = '_'.join([hex(ord(c))[2:] for c in code])
    img_type = data['id'].split('-')[0]
    if not img_type.endswith('s'):
        img_type += 's'
    dst_file = f"imgs/{img_type}/{data['name']}.png"

    if data['name'] == "Garlic Armor":
        download_from_wiki(data['name'], f"imgs/{img_type}/{data['name']}_alt.png", img_size)

    elif data['name'] in SAP_WIKI_URL:
        download_from_wiki(data['name'], dst_file, img_size)
        return

    if data['name'] in WRONG_COMMITS:
        git_dir = os.path.join(path, source)
        git_cmd = ["git", "-C", git_dir, "switch", "--detach", commit]
        subprocess.run(git_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    if source == "noto-emoji":
        file_name = f"emoji_u{code}.svg"
        src_file = os.path.join(path, source, "svg", file_name)

    elif source == "fxemoji":
        file_name = f"u{code.upper()}-{data['image']['name']}.svg"
        src_file = os.path.join(path, source, "svgs/FirefoxEmoji", file_name)

    elif source == "twemoji":
        file_name = f"{code}.svg"
        src_file = os.path.join(path, source, "assets/svg", file_name)

    print(f"Processing {data['name']} ({src_file} to {dst_file})")
    # convert_cmd = ["convert", "-background", "none", "-size", f"{img_size}x{img_size}", src_file, dst_file]
    branch_name = subprocess.run
    convert_cmd = ["inkscape", "-w", str(img_size), "-h", str(img_size), src_file, "-o", dst_file]
    result = subprocess.run(convert_cmd, capture_output=True)
    if not os.path.isfile(dst_file):
        print("An error occured !\n", result.stderr.decode())
        exit()

    if data['name'] in WRONG_COMMITS:
        git_cmd = ["git", "-C", git_dir, "branch", "--format=%(refname:short)"]
        branches = subprocess.run(git_cmd, capture_output=True).stdout.decode().split('\n')[:-1]
        branch_name = next(filter(lambda branch: 'detached' not in branch, branches))
        git_cmd = ["git", "-C", git_dir, "switch", branch_name]
        subprocess.run(git_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def download_imgs(file_name, path, img_size):
    with open(file_name, 'r') as file:
        data = json.load(file)

    os.makedirs("imgs/pets", exist_ok=True)
    for pet_data in data['pets'].values():
        download_img(pet_data, path, img_size)

    os.makedirs("imgs/status", exist_ok=True)
    for status_data in data['statuses'].values():
        download_img(status_data, path, img_size)


if __name__ == '__main__':
    # TODO: argument to ignore existing images
    # TODO: use async
    parser = argparse.ArgumentParser()
    parser.add_argument('path', type=str, help="Path to directory containing the github repository of noto-emoji, fxemoji and twemoji")
    parser.add_argument('-s', '--size', type=int, default=120, help="Size of the final png")
    args = parser.parse_args()
    download_imgs(DATA_FILE, args.path, args.size)
