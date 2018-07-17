import numpy as np
from PIL import Image
import glob
import torch
import torch.nn as nn
from torch.autograd import Variable
from torchvision import transforms
from random import randint
from torch.utils.data.dataset import Dataset
from augmentation import *
from mean_std import *

Training_MEAN = 0.4911
Training_STDEV = 0.0402


class SEMDataTrain(Dataset):
    def __init__(self, image_path, mask_path, in_size=572, out_size=388):
        """
        Args:
            image_path (str): the path where the image is located
            mask_path (str): the path where the mask is located
            option (str): decide which dataset to import
        """
        # all file names
        self.mask_arr = glob.glob(str(mask_path) + str("/*"))
        self.image_arr = glob.glob(str(image_path) + str("/*"))
        self.in_size, self.out_size = in_size, out_size
        # Calculate len
        self.data_len = len(self.mask_arr)
        # calculate mean and stdev
        self.img_mean, self.img_std = find_mean(image_path), find_stdev(image_path)

    def __getitem__(self, index):
        """Get specific data corresponding to the index
        Args:
            index (int): index of the data

        Returns:
            Tensor: specific data on index which is converted to Tensor
        """
        # Other approach using torchvision
        """ Other approach with torchvision
        single_image_name = self.image_arr[index]
        img_as_img = Image.open(single_image_name)
        img_as_np = np.asarray(img_as_img).reshape(1, 512, 512)
        # If there is an operation
        if self.trans == True:
            pass
        # Transform image to tensor
        elif self.trans != True:
            img_as_tensor = self.to_tensor(img_as_np)
        """
        # Get image
        single_image_name = self.image_arr[index]
        img_as_img = Image.open(single_image_name)
        # img_as_img.show()
        img_as_np = np.asarray(img_as_img)

        # Augmentation
        # flip {0: vertical, 1: horizontal, 2: both, 3: none}
        flip_num = 3  # randint(0, 3)
        flip_img = flip(img_as_np, flip_num)

        # Noise Determine {0: Gaussian_noise, 1: uniform_noise}
        noise_det = randint(0, 1)
        if noise_det == 0:
            # Gaussian_noise
            gaus_sd, gaus_mean = randint(0, 20), 0
            noise_img = add_gaussian_noise(flip_img, gaus_mean, gaus_sd)
        else:
            # uniform_noise
            l_bound, u_bound = randint(-20, 0), randint(0, 20)
            noise_img = add_uniform_noise(flip_img, l_bound, u_bound)

        # Brightness
        pix_add = randint(-20, 20)
        bright_img = change_brightness(noise_img, pix_add)

        # Elastic distort {0: distort, 1:no distort}
        distort_det = randint(0, 1)
        if distort_det == 0:
            # sigma = 4, alpha = 34
            aug_img, s = add_elastic_transform(bright_img, alpha=34, sigma=4)
        else:
            aug_img = bright_img

        # Crop and pad the image
        cropped_img, y_loc, x_loc = crop_pad_train(
            aug_img, in_size=self.in_size, out_size=self.out_size)

        # Sanity Check for Cropped image
        img = Image.fromarray(cropped_img)
        img.show()
        print(flip_num, noise_det, distort_det, pix_add, y_loc, x_loc)

        # Normalize the image
        norm_img = normalize(cropped_img, mean=self.img_mean, std=self.img_std)
        img_as_np = np.expand_dims(norm_img, axis=0)  # add additional dimension
        img_as_tensor = torch.from_numpy(img_as_np).float()  # Convert numpy array to tensor

        # Get mask
        single_mask_name = self.mask_arr[index]
        msk_as_img = Image.open(single_mask_name)
        # msk_as_img.show()
        msk_as_np = np.asarray(msk_as_img)

        # flip the mask with respect to image
        flip_msk = flip(msk_as_np, flip_num)

        # elastic_transform of mask with respect to image
        if distort_det == 0:
            # sigma = 4, alpha = 34
            aug_msk, _ = add_elastic_transform(flip_msk, alpha=34, sigma=4, seed=s)
            aug_msk = zero_255_image(aug_msk)  # images only with 0 and 255
        else:
            aug_msk = flip_msk

        # Crop the mask
        cropped_msk = aug_msk[y_loc:y_loc+self.out_size, x_loc:x_loc+self.out_size]

        # Sanity Check for mask
        img2 = Image.fromarray(cropped_msk)
        img2.show()

        # Normalize mask to only 0 and 1
        cropped_msk = cropped_msk/255
        msk_as_np = np.expand_dims(cropped_msk/255, axis=0)  # add additional dimension
        msk_as_tensor = torch.from_numpy(msk_as_np).float()  # Convert numpy array to tensor

        return (img_as_tensor, msk_as_tensor)

    def __len__(self):
        """
        Returns:
            length (int): length of the data
        """
        return self.data_len


class SEMDataTest(Dataset):

    def __init__(self, image_path, mask_path, in_size=572, out_size=388):
        '''
        Args:
            image_path = path where test images are located
            mask_path = path where test masks are located
        '''
        # paths to all images and masks
        self.mask_arr = glob.glob(str(mask_path) + str("/*"))
        self.image_arr = glob.glob(str(image_path) + str("/*"))
        self.in_size = in_size
        self.out_size = out_size

    def __getitem__(self, index):
        """Get specific data corresponding to the index
        Args:
            index : an integer variable that calls (indext)th image in the
                    path

        Returns:
            Tensor: 4 cropped data on index which is converted to Tensor
        """
        single_image = self.image_arr[index]
        img_as_img = Image.open(single_image)

        # Convert the image into numpy array
        img_as_numpy = np.asarray(img_as_img)

        # Make 4 cropped image (in numpy array form) using values calculated above
        # Cropped images will also have paddings to fit the model.

        cropped_padded = crop_pad_test(img_as_numpy,
                                       in_size=self.in_size,
                                       out_size=self.out_size)

        top_left = cropped_padded[0]
        top_right = cropped_padded[1]
        bottom_left = cropped_padded[2]
        bottom_right = cropped_padded[3]

        '''
        # SANITY CHECK: SEE THE CROPPED IMAGES

        topleft_img = Image.fromarray(top_left)
        topright_img = Image.fromarray(top_right)
        bottomleft_img = Image.fromarray(bottom_left)
        bottomright_img = Image.fromarray(bottom_right)
        topleft_img.show()
        topright_img.show()
        bottomleft_img.show()
        bottomright_img.show()
        '''

        # Normalize the cropped arrays
        topleft_normalized = normalize(top_left, mean=Training_MEAN, std=Training_STDEV)
        topright_normalized = normalize(top_left, mean=Training_MEAN, std=Training_STDEV)
        bottomleft_normalized = normalize(top_left, mean=Training_MEAN, std=Training_STDEV)
        bottomright_normalized = normalize(top_left, mean=Training_MEAN, std=Training_STDEV)

        # Convert 4 cropped numpy arrays into tensor
        #img_as_numpy = np.expand_dims(img_as_img, axis=0)
        top_left_tensor = torch.from_numpy(topleft_normalized).float()
        top_right_tensor = torch.from_numpy(topright_normalized).float()
        bottom_left_tensor = torch.from_numpy(bottomleft_normalized).float()
        bottom_right_tensor = torch.from_numpy(bottomright_normalized).float()

        return (top_left_tensor, top_right_tensor, bottom_left_tensor, bottom_right_tensor)

    def __len__(self):

        return self.data_len


if __name__ == "__main__":

    custom_mnist_from_file_train = SEMDataTrain(
        '../data/train/images', '../data/train/masks')
    custom_mnist_from_file_test = SEMDataTest(
        '../data/test/images/', '../data/test/masks')

    imag_1 = custom_mnist_from_file_train.__getitem__(0)
    imag_2 = custom_mnist_from_file_test.__getitem__(0)
    print(imag_2)
