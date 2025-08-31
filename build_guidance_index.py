# Tool to preprocess guidance docs

import argparse

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    print(f'Building guidance index from {args.source} -> {args.out}')
