from __future__ import print_function
import caffe
from caffe.model_libs import *
from google.protobuf import text_format

import math
import os
import shutil
import stat
import subprocess
import sys
import numpy as np

import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--batch_size", type=int, default=4, help="training batch size")
parser.add_argument("--num_accelerators", type=int, default=1, help="number of accelerators used for training")
args = parser.parse_args()


# Methods provided for combining features, 'Eltwise', EltwiseProd'
#deconv_combine_method='EltwiseSUM'
deconv_combine_method='EltwisePROD'

#add extra layers on top of a "base" network (e.g. VGGNet or Inception).
def AddExtraLayers(net, use_batchnorm=True,
        lr_mult=1, decay_mult=1, **bn_param):

    use_relu = True

    # Add additional layers to handle atrous effect.
    last_layer = net.keys()[-1]

    # 20 x 20
    ResBody(net, last_layer, '6', out2a=256, out2b=256, out2c=1024, stride=2, kernel=2,
            use_branch1=True, lr_mult=lr_mult, decay_mult=decay_mult, **bn_param)

    # 10 x 10
    ResBody(net, 'res6', '7', out2a=256, out2b=256, out2c=1024, stride=2, kernel=2,
            use_branch1=True, lr_mult=lr_mult, decay_mult=decay_mult, **bn_param)

    # 5 x 5
    ResBody(net, 'res7', '8', out2a=256, out2b=256, out2c=1024, stride=1, kernel=3, 
            use_branch1=True, lr_mult=lr_mult, decay_mult=decay_mult, **bn_param)


    # 3 x 3
    ResBody(net, 'res8', '9', out2a=256, out2b=256, out2c=1024, stride=1, kernel=3, 
            use_branch1=True, lr_mult=lr_mult, decay_mult=decay_mult, **bn_param)

    # 1 x 1
    return net

def CombineFeature(net, name,  deconv_layer, forward_layer, method='EltwiseSUM', **bn_param):
    name = '{}_{}'.format(name, method)
    name_deconv = '{}_pre'.format(deconv_layer)
    name_forward1 = '{}_pre1'.format(forward_layer)
    name_forward2 = '{}_pre2'.format(forward_layer)
    
    ConvBNLayer(net, forward_layer, name_forward1 , True, True, 512,3,1, 1, **bn_param)
    ConvBNLayer(net, name_forward1, name_forward2 , True, False, 512,3,1, 1, **bn_param)
    ConvBNLayer(net, deconv_layer, name_deconv , True, False, 512,3,1, 1, **bn_param)
    
    if method == "EltwiseSUM":
        net[name] = L.Eltwise(net[name_deconv], net[name_forward2], eltwise_param={'operation':P.Eltwise.SUM})
    elif method == "EltwisePROD":
        net[name] = L.Eltwise(net[name_deconv], net[name_forward2], eltwise_param={'operation':P.Eltwise.PROD})
    else:
        assert False, "Wrong method name :{}".format(method) 

    relu_name = "{}_relu".format(name)
    net[relu_name] = L.ReLU(net[name])

    return relu_name


def AddDeconvLayers(net, forward_layers, use_batchnorm=True, **bn_param):
    use_relu = True
    last_layer = net.keys()[-1]
    
    output_layers = []
    assert len(forward_layers) == 5, "The number of forward layers should be 5."

    #3x3
    DeconvBNLayer(net, 'res9', 'deconv_8', False, False, 512, 3, 0, 1)
    name = CombineFeature(net, 'combined_8','deconv_8', forward_layers[0],
            method=deconv_combine_method, **bn_param)
    output_layers.append(name)

    #5x5
    DeconvBNLayer(net, name, 'deconv_7', False, False, 512, 3, 0, 1)
    name = CombineFeature(net, 'combined_7','deconv_7', forward_layers[1], 
            method=deconv_combine_method, **bn_param)
    output_layers.append(name)

    #10x10
    DeconvBNLayer(net, name, 'deconv_6', False, False, 512, 2, 0, 2)
    name = CombineFeature(net, 'combined_6','deconv_6', forward_layers[2], 
            method=deconv_combine_method, **bn_param)
    output_layers.append(name)

    #20x20
    DeconvBNLayer(net, name, 'deconv_5', False, False, 512, 2, 0, 2)
    name = CombineFeature(net, 'combined_5','deconv_5', forward_layers[3],
            method=deconv_combine_method, **bn_param)
    output_layers.append(name)

    # 40x40
    DeconvBNLayer(net, name, 'deconv_3', False, False, 512,  2, 0, 2)
    name = CombineFeature(net, 'combined_3','deconv_3', forward_layers[4], 
            method=deconv_combine_method, **bn_param)
    output_layers.append(name)

    return output_layers[::-1]


### Modify the following parameters accordingly ###
# The directory which contains the caffe code.
# We assume you are running the script at the CAFFE_ROOT.
caffe_root = os.getcwd()

# Set true if you want to start training right after generating all files.
run_soon = True
# Set true if you want to load from most recently saved snapshot.
# Otherwise, we will load from the pretrain_model defined below.
resume_training = False
# If true, Remove old model files.
remove_old_models = False

# The database file for training data. Created by data/coco/create_data.sh
#train_data = "examples/VOC0712/VOC0712_trainval_lmdb"
train_data = "VOC0712/VOCdevkit/VOC0712/lmdb/VOC0712_trainval_lmdb"
# The database file for testing data. Created by data/coco/create_data.sh
#test_data = "examples/VOC0712/VOC2007_test_lmdb"
test_data = "VOC0712/VOCdevkit/VOC0712/lmdb/VOC0712_test_lmdb"
# Specify the batch sampler.
resize_width = 321
resize_height = 321
resize = "{}x{}".format(resize_width, resize_height)
batch_sampler = [
        {
                'sampler': {
                        },
                'max_trials': 1,
                'max_sample': 1,
        },
        {
                'sampler': {
                        'min_scale': 0.3,
                        'max_scale': 1.0,
                        'min_aspect_ratio': 0.5,
                        'max_aspect_ratio': 2.0,
                        },
                'sample_constraint': {
                        'min_jaccard_overlap': 0.1,
                        },
                'max_trials': 50,
                'max_sample': 1,
        },
        {
                'sampler': {
                        'min_scale': 0.3,
                        'max_scale': 1.0,
                        'min_aspect_ratio': 0.5,
                        'max_aspect_ratio': 2.0,
                        },
                'sample_constraint': {
                        'min_jaccard_overlap': 0.3,
                        },
                'max_trials': 50,
                'max_sample': 1,
        },
        {
                'sampler': {
                        'min_scale': 0.3,
                        'max_scale': 1.0,
                        'min_aspect_ratio': 0.5,
                        'max_aspect_ratio': 2.0,
                        },
                'sample_constraint': {
                        'min_jaccard_overlap': 0.5,
                        },
                'max_trials': 50,
                'max_sample': 1,
        },
        {
                'sampler': {
                        'min_scale': 0.3,
                        'max_scale': 1.0,
                        'min_aspect_ratio': 0.5,
                        'max_aspect_ratio': 2.0,
                        },
                'sample_constraint': {
                        'min_jaccard_overlap': 0.7,
                        },
                'max_trials': 50,
                'max_sample': 1,
        },
        {
                'sampler': {
                        'min_scale': 0.3,
                        'max_scale': 1.0,
                        'min_aspect_ratio': 0.5,
                        'max_aspect_ratio': 2.0,
                        },
                'sample_constraint': {
                        'min_jaccard_overlap': 0.9,
                        },
                'max_trials': 50,
                'max_sample': 1,
        },
        {
                'sampler': {
                        'min_scale': 0.3,
                        'max_scale': 1.0,
                        'min_aspect_ratio': 0.5,
                        'max_aspect_ratio': 2.0,
                        },
                'sample_constraint': {
                        'max_jaccard_overlap': 1.0,
                        },
                'max_trials': 50,
                'max_sample': 1,
        },
        ]
train_transform_param = {
        'mirror': True,
        'mean_value': [104, 117, 123],
        'resize_param': {
                'prob': 1,
                'resize_mode': P.Resize.WARP,
                'height': resize_height,
                'width': resize_width,
                'interp_mode': [
                        P.Resize.LINEAR,
                        P.Resize.AREA,
                        P.Resize.NEAREST,
                        P.Resize.CUBIC,
                        P.Resize.LANCZOS4,
                        ],
                },
        'distort_param': {
                'brightness_prob': 0.5,
                'brightness_delta': 32,
                'contrast_prob': 0.5,
                'contrast_lower': 0.5,
                'contrast_upper': 1.5,
                'hue_prob': 0.5,
                'hue_delta': 18,
                'saturation_prob': 0.5,
                'saturation_lower': 0.5,
                'saturation_upper': 1.5,
                'random_order_prob': 0.0,
                },
        'expand_param': {
                'prob': 0.5,
                'max_expand_ratio': 4.0,
                },
        'emit_constraint': {
            'emit_type': caffe_pb2.EmitConstraint.CENTER,
            }
        }
test_transform_param = {
        'mean_value': [104, 117, 123],
        'resize_param': {
                'prob': 1,
                'resize_mode': P.Resize.WARP,
                'height': resize_height,
                'width': resize_width,
                'interp_mode': [P.Resize.LINEAR],
                },
        }

# A learning rate for batch_size = 1, num_gpus = 1.
base_lr = 0.00004

# Modify the job name if you want.
job_name = "DSSD_VOC07_FT_{}".format(resize)
#job_name = "SSD_test{}".format(resize)
# The name of the model. Modify it if you want.
model_name = "ResNet-101_VOC0712_{}".format(job_name)

# Directory which stores the model .prototxt file.
save_dir = "models/ResNet-101/VOC0712/{}_score".format(job_name)
# Directory which stores the snapshot of models.
snapshot_dir = "models/ResNet-101/VOC0712/{}".format(job_name)
# Directory which stores the job script and log file.
job_dir = "jobs/ResNet-101/VOC0712/{}_score".format(job_name)
# Directory which stores the detection results.
output_result_dir = "./results/VOC0712/{}_score/Main".format(job_name)

# model definition files.
train_net_file = "{}/train.prototxt".format(save_dir)
test_net_file = "{}/test.prototxt".format(save_dir)
deploy_net_file = "{}/deploy.prototxt".format(save_dir)
solver_file = "{}/solver.prototxt".format(save_dir)
test_solver_file = "{}/test_solver.prototxt".format(save_dir)
# snapshot prefix.
snapshot_prefix = "{}/{}".format(snapshot_dir, model_name)
# job script path.
job_file = "{}/{}.sh".format(job_dir, model_name)

# Stores the test image names and sizes. Created by data/coco/create_list.sh
name_size_file = "data/VOC0712/test_name_size.txt"
# The pretrained ResNet101 model from https://github.com/KaimingHe/deep-residual-networks.
#pretrain_model = "models/ResNet-101/ResNet-101-model.caffemodel"
#pretrain_model = "models/ResNet-101/VOC0712/SSD_VOC07_321x321/ResNet-101_VOC0712_SSD_VOC07_321x321_iter_80000.caffemodel"
pretrain_model = "models/ResNet-101/VOC0712/DSSD_VOC07_321x321/ResNet-101_VOC0712_DSSD_VOC07_321x321_iter_1000.caffemodel"


# Stores LabelMapItem.
label_map_file = "data/VOC0712/labelmap_voc.prototxt"

# MultiBoxLoss parameters.
num_classes = 21
share_location = True
background_label_id=0
train_on_diff_gt = True
normalization_mode = P.Loss.VALID
code_type = P.PriorBox.CENTER_SIZE
ignore_cross_boundary_bbox = False
mining_type = P.MultiBoxLoss.MAX_NEGATIVE
neg_pos_ratio = 3.
loc_weight = (neg_pos_ratio + 1.) / 4.
#loc_weight = 1.
multibox_loss_param = {
    'loc_loss_type': P.MultiBoxLoss.SMOOTH_L1,
    'conf_loss_type': P.MultiBoxLoss.SOFTMAX,
    'loc_weight': loc_weight,
    'num_classes': num_classes,
    'share_location': share_location,
    'match_type': P.MultiBoxLoss.PER_PREDICTION,
    'overlap_threshold': 0.5,
    'use_prior_for_matching': True,
    'background_label_id': background_label_id,
    'use_difficult_gt': train_on_diff_gt,
    'mining_type': mining_type,
    'neg_pos_ratio': neg_pos_ratio,
    'neg_overlap': 0.5,
    'code_type': code_type,
    'ignore_cross_boundary_bbox': ignore_cross_boundary_bbox,
    }
loss_param = {
    'normalization': normalization_mode,
    }

# parameters for generating priors.
# minimum dimension of input image
min_dim = 321
# res3b3_relu ==> 40 x 40
# res5c_relu ==> 20 x 20
# res6_relu ==> 10 x 10
# res7_relu ==> 5 x 5
# res8_relu ==> 3 x 3
# res9_relu ==> 1x1
mbox_source_layers = ['res3b3_relu', 'res5c_relu', 'res6_relu', 'res7_relu', 'res8_relu', 'res9_relu']
# in percent %
min_ratio = 20
max_ratio = 95
step = int(math.floor((max_ratio - min_ratio) / (len(mbox_source_layers) - 2)))
min_sizes = []
max_sizes = []
for ratio in range(min_ratio, max_ratio + 1, step):
  min_sizes.append(min_dim * ratio / 100.)
  max_sizes.append(min_dim * (ratio + step) / 100.)
min_sizes = [min_dim * 10 / 100.] + min_sizes
max_sizes = [min_dim * 20 / 100.] + max_sizes
steps = [8, 16, 32, 64, 64, 321]
starts = [2.5, 2.5, 10.5, 26.5, 90.5, 160.5]
kmeans_ratios = [1.60, 2.0, 3.0]
aspect_ratios=[]
for i in range(6):
    aspect_ratios.append(kmeans_ratios)

inter_layer_depth = [[256], [256], [256], [256], [256], [256]]
normalizations=[]
prediction_kernels= [5,5,3,3,3,3]
prediction_pads = [2,2,1,1,1,1]

# variance used to encode/decode prior bboxes.
if code_type == P.PriorBox.CENTER_SIZE:
  prior_variance = [0.1, 0.1, 0.2, 0.2]
else:
  prior_variance = [0.1]
flip = True
clip = False


deconv_mbox_source_layers = ['resd3_relu', 'resd5_relu', 'resd6_relu', 'resd7_relu', 'resd8_relu']

# Solver parameters.
# Defining which GPUs to use.
#gpus = "0,1,2,3"
gpus = "0"
for i in range(args.num_accelerators):
    if i != 0:
        gpus = gpus + "," + str(i)
gpulist = gpus.split(",")
num_gpus = len(gpulist)


# Divide the mini-batch to different GPUs.
batch_size = args.batch_size * args.num_accelerators
accum_batch_size = args.batch_size * args.num_accelerators
iter_size = accum_batch_size / batch_size
solver_mode = P.Solver.CPU
device_id = 0
batch_size_per_device = batch_size
if num_gpus > 0:
  batch_size_per_device = int(math.ceil(float(batch_size) / num_gpus))
  iter_size = int(math.ceil(float(accum_batch_size) / (batch_size_per_device * num_gpus)))
  solver_mode = P.Solver.GPU
  device_id = int(gpulist[0])

print("batch_size: ", batch_size)
print("accum_batch_size: ", accum_batch_size)
print("gpus: ", gpus)
print("num_gpus: ", num_gpus)

if normalization_mode == P.Loss.NONE:
  base_lr /= batch_size_per_device
elif normalization_mode == P.Loss.VALID:
  base_lr *= 25. / loc_weight
elif normalization_mode == P.Loss.FULL:
  # Roughly there are 2000 prior bboxes per image.
  # TODO(weiliu89): Estimate the exact # of priors.
  base_lr *= 2000.

# Evaluate on whole test set.
num_test_image = 4952
test_batch_size = args.batch_size
test_iter = num_test_image // test_batch_size

solver_param = {
    # Train parameters
    'base_lr': base_lr*0.1,
    'weight_decay': 0.0005,
    'lr_policy': "multistep",
    'stepvalue': [20000],
    'gamma': 0.1,
    'momentum': 0.9,
    'iter_size': iter_size,
    'max_iter': 0,
    'snapshot': 0,
    'display': 10,
    'average_loss': 10,
    'type': "SGD",
    'solver_mode': solver_mode,
    'device_id': device_id,
    'debug_info': False,
    'snapshot_after_train': False,
    # Test parameters
    'test_iter': [test_iter],
    'test_interval': 10000,
    'eval_type': "detection",
    'ap_version': "11point",
    'test_initialization': True,
    }

# test_solver_param
test_solver_param = solver_param.copy()
test_solver_param['test_iter'] = [test_iter]
test_solver_param['test_interval'] = 10000
test_solver_param['eval_type'] = "detection"
test_solver_param['ap_version'] = "11point"
test_solver_param['test_initialization'] = True
test_solver_param['max_iter'] = 0
test_solver_param['device_id'] = 0
test_solver_param['snapshot_after_train']= False
test_solver_param['solver_mode'] = P.Solver.GPU


# parameters for generating detection output.
det_out_param = {
    'num_classes': num_classes,
    'share_location': share_location,
    'background_label_id': background_label_id,
    'nms_param': {'nms_threshold': 0.45, 'top_k': 400},
    'save_output_param': {
        'output_directory': output_result_dir,
        'output_name_prefix': "comp4_det_test_",
        'output_format': "VOC",
        'label_map_file': label_map_file,
        'name_size_file': name_size_file,
        'num_test_image': num_test_image,
        },
    'keep_top_k': 200,
    'confidence_threshold': 0.01,
    'code_type': code_type,
    }

# parameters for evaluating detection results.
det_eval_param = {
    'num_classes': num_classes,
    'background_label_id': background_label_id,
    'overlap_threshold': 0.5,
    'evaluate_difficult_gt': False,
    'name_size_file': name_size_file,
    }

### Hopefully you don't need to change the following ###
# Check file.
check_if_exist(train_data)
check_if_exist(test_data)
check_if_exist(label_map_file)
check_if_exist(pretrain_model)
make_if_not_exist(save_dir)
make_if_not_exist(job_dir)
make_if_not_exist(snapshot_dir)

# Create train net.
net = caffe.NetSpec()
net.data, net.label= CreateAnnotatedDataLayer(train_data, batch_size=batch_size_per_device,
        train=True, output_label=True, label_map_file=label_map_file,
        transform_param=train_transform_param, batch_sampler=batch_sampler)

# Freeze all the Batch Normalization layers (including Scale Layer)
bn_param={'use_global_stats': True}
ResNet101Body(net, from_layer='data', use_pool5=False, use_dilation_conv5=True,
            lr_mult=1, decay_mult=1, **bn_param)

# Use batch norm for the newly added layers.
AddExtraLayers(net, use_batchnorm=True, lr_mult=1, decay_mult=1, **bn_param)

deconv_layers = AddDeconvLayers(net, mbox_source_layers[4::-1], use_batchnorm=True, **bn_param)

deconv_feature_layers = CreateMultiBoxHead(net, 
        from_layers=deconv_layers + [mbox_source_layers[-1]],
        use_batchnorm=False,
        inter_layer_depth=inter_layer_depth, **bn_param)



#Don't use batch norm for location/confidence prediction layers.
mbox_layers = CreateMultiBoxOutput(net, data_layer='data', 
        from_layers= deconv_feature_layers,
        use_batchnorm=False,
        min_sizes=min_sizes, max_sizes=max_sizes, aspect_ratios=aspect_ratios,
        steps=steps, starts=starts, num_classes=num_classes,
        share_location=share_location,
        flip=flip, clip=clip, prior_variance=prior_variance,  
        inter_layer_depth=inter_layer_depth,
        kernel_sizes=prediction_kernels, pads=prediction_pads, 
        conf_postfix='new', loc_postfix='new' )


# Create the MultiBoxLossLayer.
name = "mbox_loss"
mbox_layers.append(net.label)
net[name] = L.MultiBoxLoss(*mbox_layers, multibox_loss_param=multibox_loss_param,
        loss_param=loss_param, include=dict(phase=caffe_pb2.Phase.Value('TRAIN')),
        propagate_down=[True, True, False, False])

with open(train_net_file, 'w') as f:
    print('name: "{}_train"'.format(model_name), file=f)
    print(net.to_proto(), file=f)
shutil.copy(train_net_file, job_dir)

# Create test net.
net = caffe.NetSpec()
net.data, net.label = CreateAnnotatedDataLayer(test_data, batch_size=test_batch_size,
        train=False, output_label=True, label_map_file=label_map_file,
        transform_param=test_transform_param)

# Freeze the Encoder Part of SSD 
bn_param={'use_global_stats': True}
ResNet101Body(net, from_layer='data', use_pool5=False, use_dilation_conv5=True,
            lr_mult=1, decay_mult=1, **bn_param)

# Use batch norm for the newly added layers.
AddExtraLayers(net, use_batchnorm=True, lr_mult=1, decay_mult=1, **bn_param)

deconv_layers = AddDeconvLayers(net, mbox_source_layers[4::-1], use_batchnorm=True, **bn_param)

deconv_feature_layers = CreateMultiBoxHead(net, 
        from_layers=deconv_layers + [mbox_source_layers[-1]],
        use_batchnorm=False,
        inter_layer_depth=inter_layer_depth, **bn_param)



#Don't use batch norm for location/confidence prediction layers.
mbox_layers = CreateMultiBoxOutput(net, data_layer='data', 
        from_layers=deconv_feature_layers,
        use_batchnorm=False,
        min_sizes=min_sizes, max_sizes=max_sizes, aspect_ratios=aspect_ratios,
        steps=steps, starts=starts, num_classes=num_classes,
        share_location=share_location,
        flip=flip, clip=clip, prior_variance=prior_variance,  
        inter_layer_depth=inter_layer_depth,
        kernel_sizes=prediction_kernels, pads=prediction_pads,
        conf_postfix='new', loc_postfix='new' )


conf_name = "mbox_conf"
if multibox_loss_param["conf_loss_type"] == P.MultiBoxLoss.SOFTMAX:
  reshape_name = "{}_reshape".format(conf_name)
  net[reshape_name] = L.Reshape(net[conf_name], shape=dict(dim=[0, -1, num_classes]))
  softmax_name = "{}_softmax".format(conf_name)
  net[softmax_name] = L.Softmax(net[reshape_name], axis=2)
  flatten_name = "{}_flatten".format(conf_name)
  net[flatten_name] = L.Flatten(net[softmax_name], axis=1)
  mbox_layers[1] = net[flatten_name]
elif multibox_loss_param["conf_loss_type"] == P.MultiBoxLoss.LOGISTIC:
  sigmoid_name = "{}_sigmoid".format(conf_name)
  net[sigmoid_name] = L.Sigmoid(net[conf_name])
  mbox_layers[1] = net[sigmoid_name]

net.detection_out = L.DetectionOutput(*mbox_layers,
    detection_output_param=det_out_param,
    include=dict(phase=caffe_pb2.Phase.Value('TEST')))
net.detection_eval = L.DetectionEvaluate(net.detection_out, net.label,
    detection_evaluate_param=det_eval_param,
    include=dict(phase=caffe_pb2.Phase.Value('TEST')))



with open(test_net_file, 'w') as f:
    print('name: "{}_test"'.format(model_name), file=f)
    print(net.to_proto(), file=f)
shutil.copy(test_net_file, job_dir)


# Create deploy net.
# Remove the first and last layer from test net.
deploy_net = net
with open(deploy_net_file, 'w') as f:
    net_param = deploy_net.to_proto()
    # Remove the first (AnnotatedData) and last (DetectionEvaluate) layer from test net.
    del net_param.layer[0]
    del net_param.layer[-1]
    net_param.name = '{}_deploy'.format(model_name)
    net_param.input.extend(['data'])
    net_param.input_shape.extend([
        caffe_pb2.BlobShape(dim=[1, 3, resize_height, resize_width])])
    print(net_param, file=f)
shutil.copy(deploy_net_file, job_dir)

# Create solver.
solver = caffe_pb2.SolverParameter(
        train_net=train_net_file,
        test_net=[test_net_file],
        snapshot_prefix=snapshot_prefix,
        **solver_param)

with open(solver_file, 'w') as f:
    print(solver, file=f)
shutil.copy(solver_file, job_dir)

# Create test solver.
test_solver = caffe_pb2.SolverParameter(
        train_net=train_net_file,
        test_net=[test_net_file],
        snapshot_prefix=snapshot_prefix,
        **test_solver_param)
with open(test_solver_file, 'w') as f:
    print(test_solver, file=f)


max_iter = 0
# Find most recent snapshot.
for file in os.listdir(snapshot_dir):
  if file.endswith(".solverstate"):
    basename = os.path.splitext(file)[0]
    iter = int(basename.split("{}_iter_".format(model_name))[1])
    if iter > max_iter:
      max_iter = iter

train_src_param = '--weights="{}" \\\n'.format(pretrain_model)
if resume_training:
  if max_iter > 0:
    train_src_param = '--snapshot="{}_iter_{}.solverstate" \\\n'.format(snapshot_prefix, max_iter)

if remove_old_models:
  # Remove any snapshots smaller than max_iter.
  for file in os.listdir(snapshot_dir):
    if file.endswith(".solverstate"):
      basename = os.path.splitext(file)[0]
      iter = int(basename.split("{}_iter_".format(model_name))[1])
      if max_iter > iter:
        os.remove("{}/{}".format(snapshot_dir, file))
    if file.endswith(".caffemodel"):
      basename = os.path.splitext(file)[0]
      iter = int(basename.split("{}_iter_".format(model_name))[1])
      if max_iter > iter:
        os.remove("{}/{}".format(snapshot_dir, file))

# Create job file.
with open(job_file, 'w') as f:
  f.write('cd {}\n'.format(caffe_root))
  f.write('./build/tools/caffe train \\\n')
  f.write('--solver="{}" \\\n'.format(solver_file))
  f.write('--weights="{}" \\\n'.format(pretrain_model))
  f.write(train_src_param)
  if solver_param['solver_mode'] == P.Solver.GPU:
    f.write('--gpu {} 2>&1 | tee {}/{}.log\n'.format(gpus, job_dir, model_name))
  else:
    f.write('2>&1 | tee {}/{}.log\n'.format(job_dir, model_name))

# Copy the python script to job_dir.
py_file = os.path.abspath(__file__)
shutil.copy(py_file, job_dir)

# Run the job.
os.chmod(job_file, stat.S_IRWXU)
if run_soon:
  subprocess.call(job_file, shell=True)
