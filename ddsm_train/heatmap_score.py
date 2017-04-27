import argparse
import os, sys
import pickle
import numpy as np
import pandas as pd
from numpy.random import RandomState
from sklearn.model_selection import train_test_split
# from keras.models import load_model
from dm_image import get_prob_heatmap
from dm_keras_ext import get_dl_model
from dm_multi_gpu import make_parallel
import warnings, exceptions
warnings.filterwarnings('ignore', category=exceptions.UserWarning)


def run(img_folder, dl_state, 
        img_height=4096, img_scale=255., equalize_hist=False, 
        featurewise_center=False, featurewise_mean=71.8,
        net='vgg19', batch_size=128, patch_size=256, stride=8,
        pat_csv='./full_img/pat.csv', pat_list=None,
        out='./output/prob_heatmap.pkl'):
    '''Sweep mammograms with trained DL model to create prob heatmaps
    '''
    # Read some env variables.
    random_seed = int(os.getenv('RANDOM_SEED', 12345))
    rng = RandomState(random_seed)  # an rng used across board.
    gpu_count = int(os.getenv('NUM_GPU_DEVICES', 1))

    # Get image and label lists.
    df = pd.read_csv(pat_csv, header=0)
    df = df.set_index(['patient_id', 'side'])
    df.sort_index(inplace=True)
    if pat_list is not None:
        pat_ids = pd.read_csv(pat_list, header=0).values.ravel()
        pat_ids = pat_ids.tolist()
        print "Read %d patient IDs" % (len(pat_ids))
        df = df.loc[pat_ids]

    # Load DL model, preprocess.
    print "Load patch classifier:", dl_state; sys.stdout.flush()
    dl_model, preprocess_input, _ = get_dl_model(
        net, use_pretrained=True, resume_from=dl_state)
    if gpu_count > 1:
        print "Make the model parallel on %d GPUs" % (gpu_count)
        sys.stdout.flush()
        dl_model, _ = make_parallel(dl_model, gpu_count)
        parallelized = True
    else:
        parallelized = False
    if featurewise_center:
        preprocess_input = None

    # Sweep the whole images and classify patches.
    def const_filename(pat, side, view):
        basename = '_'.join([pat, side, view]) + '.png'
        return os.path.join(img_folder, basename)

    print "Generate prob heatmaps"; sys.stdout.flush()
    heatmaps = []
    cases_seen = 0
    nb_cases = len(df.index.unique())
    for i, (pat,side) in enumerate(df.index.unique()):
        ## DEBUG ##
        #if i >= 10:
        #    break
        ## DEBUG ##
        cancer = df.loc[pat].loc[side]['cancer']
        cc_fn = const_filename(pat, side, 'CC')
        if os.path.isfile(cc_fn):
            cc_hm = get_prob_heatmap(
                cc_fn, img_height, img_scale, patch_size, stride, 
                dl_model, batch_size, featurewise_center=featurewise_center, 
                featurewise_mean=featurewise_mean, preprocess=preprocess_input, 
                parallelized=parallelized, equalize_hist=equalize_hist)
        else:
            cc_hm = None
        mlo_fn = const_filename(pat, side, 'MLO')
        if os.path.isfile(mlo_fn):
            mlo_hm = get_prob_heatmap(
                mlo_fn, img_height, img_scale, patch_size, stride, 
                dl_model, batch_size, featurewise_center=featurewise_center, 
                featurewise_mean=featurewise_mean, preprocess=preprocess_input, 
                parallelized=parallelized, equalize_hist=equalize_hist)
        else:
            mlo_hm = None
        heatmaps.append({'patient_id':pat, 'side':side, 'cancer':cancer, 
                         'cc':cc_hm, 'mlo':mlo_hm})
        print "scored %d/%d cases" % (i + 1, nb_cases)
        sys.stdout.flush()
    print "Done."

    # Save the result.
    print "Saving result to external files.",
    sys.stdout.flush()
    pickle.dump(heatmaps, open(out, 'w'))
    print "Done."


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description="heatmap scoring")
    parser.add_argument("img_folder", type=str)
    parser.add_argument("dl_state", type=str)
    parser.add_argument("--img-height", "-ih", dest="img_height", type=int, default=4096)
    parser.add_argument("--img-scale", "-ic", dest="img_scale", type=float, default=255.)
    parser.add_argument("--equalize-hist", dest="equalize_hist", action="store_true")
    parser.add_argument("--no-equalize-hist", dest="equalize_hist", action="store_false")
    parser.set_defaults(equalize_hist=False)
    parser.add_argument("--featurewise-center", dest="featurewise_center", action="store_true")
    parser.add_argument("--no-featurewise-center", dest="featurewise_center", action="store_false")
    parser.set_defaults(featurewise_center=False)
    parser.add_argument("--featurewise-mean", dest="featurewise_mean", type=float, default=71.8)
    parser.add_argument("--net", dest="net", type=str, default="vgg19")
    parser.add_argument("--batch-size", dest="batch_size", type=int, default=128)
    parser.add_argument("--patch-size", dest="patch_size", type=int, default=256)
    parser.add_argument("--stride", dest="stride", type=int, default=8)
    parser.add_argument("--pat-csv", dest="pat_csv", type=str, default="./full_img/pat.csv")
    parser.add_argument("--pat-list", dest="pat_list", type=str, default=None)
    parser.add_argument("--no-pat-list", dest="pat_list", action="store_const", const=None)
    parser.add_argument("--out", dest="out", type=str, default="./output/prob_heatmap.pkl")

    args = parser.parse_args()
    run_opts = dict(
        img_height=args.img_height,
        img_scale=args.img_scale,
        equalize_hist=args.equalize_hist,
        featurewise_center=args.featurewise_center,
        featurewise_mean=args.featurewise_mean,
        net=args.net,
        batch_size=args.batch_size,
        patch_size=args.patch_size,
        stride=args.stride,
        pat_csv=args.pat_csv,
        pat_list=args.pat_list,
        out=args.out,
    )
    print "\n"
    print "img_folder=%s" % (args.img_folder)
    print "dl_state=%s" % (args.dl_state)
    print "\n>>> Model training options: <<<\n", run_opts, "\n"
    run(args.img_folder, args.dl_state, **run_opts)















