import numpy as np
from tqdm import tqdm
import cv2
from camera_coords_to_image_intrinsic import camera_coords_to_image_intrinsic
from astropy_to_camera_extrinsic import astropy_to_camera_extrinsic
import pandas as pd
from colorama import Fore, Style

# direct shading factor is computed from 2 things: the photo and the position of the sun
# the factor must then be applied to the normal direct data (meaning the direct irradiation on the plane perpendicular to the rays) and not on a plane perpendicular to ground
def compute_direct_shading_factor(image, im_height, im_width, poly_incident_angle_to_radius, principal_point, orientation, inclination, estimated_fov, az_zen_array, original_time_array):
    print(f"{Fore.YELLOW}Computing hourly DIRECT shading factor...{Style.RESET_ALL}")
    complementary_direct_shading_factor = np.zeros(len(original_time_array))

    # this section is to remove the regions where the zenith goes over the horizon
    combined_array = np.vstack((range(0, len(original_time_array)), az_zen_array[0], az_zen_array[1]))
    combined_array = np.delete(combined_array, np.where(combined_array[2, :] > estimated_fov), 1)

    # now we extract them back out to use
    index_array = combined_array[0].astype(int)
    az_array = combined_array[1]
    zen_array = combined_array[2]

    # use the extrinsic function to compute the solar homo coords in cam's reference
    camera_homo_coords = astropy_to_camera_extrinsic([az_array,zen_array], orientation, inclination)
    image_coords = camera_coords_to_image_intrinsic(camera_homo_coords, poly_incident_angle_to_radius, principal_point)

    # we need the minimum image size so that we can avoid the jump from one day to another
    image_size = min(im_height, im_width)
    for i in tqdm(range(1,len(index_array))):
        # This IF check for moments where we jump to the next day. It means that we should be jumping from one side of image to another, so the length of this line will be more than half of the image height
        if (np.sqrt((image_coords[i][1] - image_coords[i-1][1]) ** 2 + (image_coords[i][0] - image_coords[i-1][0]) ** 2) < image_size / 4):
            mask_im = np.zeros(shape=(im_height, im_width, 1), dtype=np.uint8)
            mask_im = cv2.line(mask_im, (image_coords[i-1][0], image_coords[i-1][1]), (image_coords[i][0], image_coords[i][1]), 255, 20)
            masked_im = cv2.bitwise_and(image, image, mask=mask_im)

            if cv2.sumElems(mask_im)[0] != 0 :
                complementary_direct_shading_factor[index_array[i]] = cv2.sumElems(masked_im)[0] / cv2.sumElems(mask_im)[0]

    print(f"{Fore.GREEN}Done!{Style.RESET_ALL}")
    return 1-complementary_direct_shading_factor

def compute_direct_shading_factor_NASA(image, im_height, im_width, poly_incident_angle_to_radius, principal_point, image_orientation, image_inclination, inclined_surface_orientation, inclined_surface_inclination, estimated_fov, az_zen_array, original_time_array):
    print(f"{Fore.YELLOW}Computing hourly DIRECT shading factor...{Style.RESET_ALL}")

    # now there's the surface correction factor, because the direct data provided by NASA is direct NORMAL irradiance and our surface is not exactly always facing directly the sun
    # the only thing we need to know is that the way we determine the inclination and orientation of the inclined surface must be consistent with solar coordinates
    # problem: I'll ask the user to use Ox as South, Oy as East, Oz as sky... which is not consistent with the solar coords where Ox is West, Oy is South, Oz is sky
    # we'll have to perform a small rotation where we transform solar coords in solar ref to reference of the inclined surface (Ox as South, Oy as East...)

    # to make it simpler with the formula I found, I converted the variables
    z = az_zen_array[1] * np.pi / 180  # no change because Oz doesnt change after transform. This is an array
    a = (270 - az_zen_array[0]) * np.pi / 180  # change because Ox is rotated. This is an array
    alpha = inclined_surface_inclination * np.pi / 180  # scalar
    b = (90 + inclined_surface_orientation) * np.pi / 180  # scalar

    # formula could be found in CALCULATING SOLAR RADIATION FOR INCLINED SURFACES: PRACTICAL APPROACHES by John E. Hay
    # you really dont need to care about the reference frames, just remember to make the reference frame of the solar coords and the inclined surface consistent and ur good to go
    plane_adjusted_direct_coeff = (np.cos(alpha) * np.cos(z) + np.sin(alpha) * np.sin(z) * np.cos(a - b))

    # since there are solar positions in this array that corresponds to solar position at night (valid in astronomical standpoint, not very valid for solar estimation)
    # we need to perform a normalization to 0 because those values will create negative irradiance, which is weird
    # it is not actually too critical tho, because usually at night the effective irradiance is 0, so if this step is skipped there is MOST LIKELY no problem
    for i in range(len(plane_adjusted_direct_coeff)):
        if (plane_adjusted_direct_coeff[i] < 0):
            plane_adjusted_direct_coeff[i] = 0

    # create an array of complementary direct shading factor.
    # This is the EFFECTIVE irradiance received by the solar harvesting surface
    # so be sure to multiply the plane adjustment coeff to complementary_direct_shading_factor before sending out the shading factor
    complementary_direct_shading_factor = np.zeros(len(original_time_array))

    # this section is to remove the regions where the zenith goes over the horizon
    combined_array = np.vstack((range(0, len(original_time_array)), az_zen_array[0], az_zen_array[1]))
    combined_array = np.delete(combined_array, np.where(combined_array[2, :] > estimated_fov), 1)

    # now we extract them back out to use
    index_array = combined_array[0].astype(int)
    az_array = combined_array[1]
    zen_array = combined_array[2]

    # use the extrinsic function to compute the solar homo coords in cam's reference
    camera_homo_coords = astropy_to_camera_extrinsic([az_array,zen_array], image_orientation, image_inclination)
    image_coords = camera_coords_to_image_intrinsic(camera_homo_coords, poly_incident_angle_to_radius, principal_point)

    # we need the minimum image size so that we can avoid the jump from one day to another
    for i in tqdm(range(1,len(index_array))):
        # This IF check for moments where we jump to the next day.
        # the clearest indicator is when there is a clear gap in the index array, so if the index_array is still continuous then we could perform the calculation
        if (index_array[i] - index_array[i-1] == 1):
            mask_im = np.zeros(shape=(im_height, im_width, 1), dtype=np.uint8)
            mask_im = cv2.line(mask_im, (image_coords[i-1][0], image_coords[i-1][1]), (image_coords[i][0], image_coords[i][1]), 255, 50)
            masked_im = cv2.bitwise_and(image, image, mask=mask_im)

            if cv2.sumElems(mask_im)[0] != 0 :
                complementary_direct_shading_factor[index_array[i]] = cv2.sumElems(masked_im)[0] / cv2.sumElems(mask_im)[0]

    print(f"{Fore.GREEN}Done!{Style.RESET_ALL}")

    return 1-np.multiply(complementary_direct_shading_factor, plane_adjusted_direct_coeff)



# because the NASA data does not come with computed inclined surface data, we have to do it ourselves
def adjust_NASA_direct_irradiance_with_surface_position(direct_data, solar_azimuth, solar_zenith, inclined_surface_azimuth, inclined_surface_inclination):
    print(f"{Fore.YELLOW}Computing hourly DIRECT shading factor...{Style.RESET_ALL}")
    # the only thing we need to know is that the way we determine the inclination and orientation of the inclined surface must be consistent with solar coordinates
    # problem: I'll ask the user to use Ox as South, Oy as East, Oz as sky... which is not consistent with the solar coords where Ox is West, Oy is South, Oz is sky
    # we'll have to perform a small rotation where we transform solar coords in solar ref to reference of the inclined surface (Ox as South, Oy as East...)

    # to make it simpler with the formula I found, I converted the variables
    z = solar_zenith*np.pi/180        # no change because Oz doesnt change after transform. This is an array
    a = (270 - solar_azimuth)*np.pi/180         # change because Ox is rotated. This is an array
    alpha = inclined_surface_inclination*np.pi/180    # scalar
    b = (90+inclined_surface_azimuth)*np.pi/180            # scalar

    # formula could be found in CALCULATING SOLAR RADIATION FOR INCLINED SURFACES: PRACTICAL APPROACHES by John E. Hay
    # you really dont need to care about the reference frames, just remember to make the reference frame of the solar coords and the inclined surface consistent and ur good to go
    plane_adjusted_direct_data = (np.cos(alpha)*np.cos(z) + np.sin(alpha)*np.sin(z)*np.cos(a-b))*direct_data

    for i in range(len(plane_adjusted_direct_data)):
        if (plane_adjusted_direct_data[i] < 0):
            plane_adjusted_direct_data[i] = 0

    print(f"{Fore.GREEN}Done!{Style.RESET_ALL}")
    return plane_adjusted_direct_data