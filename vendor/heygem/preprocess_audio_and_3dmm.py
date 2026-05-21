#
# Created on Thu Jan 21 11:27:22 2021
#
# @author: guiji
#
import re
from PIL import Image
from scipy import signal
import time
import numpy as np
import cv2
from multiprocessing import dummy as mp

video_time = []

class op:

    def __init__(self, caped_img2, wh, scrfd_detector, scrfd_predictor, hp, lm3d_std, img_size, driver_flag):
        self.manager = mp.Manager
        self.mp_dict = self.manager().dict()
        self.img_size = img_size
        self.target_size = self.img_size + int(self.img_size / 256.0) * 10
        for idx in caped_img2.keys():
            self.mp_dict[idx] = caped_img2[idx]
        self.wh = wh
        self.scrfd_detector = scrfd_detector
        self.scrfd_predictor = scrfd_predictor
        self.hp = hp
        self.pose_threshold = [[-70, 50], [-100, 100], [-70, 70]]
        self.driver_flag = driver_flag
        self.no_face = []

    def show(self):
        for idx in self.mp_dict.keys():
            print(self.mp_dict[idx], idx)

    def get_max_face(self, face_boxes):
        if face_boxes.shape[0] == 1:
            return face_boxes[0].astype(int)
        
        # Return the box with the largest area
        return face_boxes[np.nanargmax(np.abs(face_boxes[:, 2] - face_boxes[:, 0]) * np.abs(face_boxes[:, 3] - face_boxes[:, 1]))].astype(int)


    def loc_detect_face(self, idx):
        loc_dict = self.mp_dict[idx]
        img = loc_dict['imgs_data']
        t0 = time.time()
        (face_boxes, _) = self.scrfd_detector.get_bboxes(img)
        (h, w) = img.shape[0:2]
        if face_boxes.shape[0] > 0:
            (x1, y1, x2, y2, score) = self.get_max_face(face_boxes)
            
            # Expand bounding box
            x1 = max(0, x1 - int((x2 - x1) * 0.1))
            y1 = max(0, y1)
            x2 = min(w, x2 + int((x2 - x1) * 0.1))
            y2 = min(h, y2 + int((y2 - y1) * 0.1))
            
            face_img = img[int(y1):int(y2), int(x1):int(x2)]
            pots = self.scrfd_predictor.forward(face_img)[0]
            landmarks = np.array([ [x + x1, y + y1] for x, y in pots.astype(np.int32)])
            
            (xmin, ymin, w, h) = cv2.boundingRect(np.array(landmarks))
            x_c = xmin + w / 2.0
            wh = w / h
            
            # Calculate 3DMM bounding box
            Xmin_3dmm = int(x_c - w / wh * 0.8)
            Xmax_3dmm = int(x_c + w / wh * 0.8)
            Ymin_3dmm = int(ymin - w / wh * 0.35)
            Ymax_3dmm = int(ymin + w / wh * 1.25)
            
            # Clamp coordinates to image boundaries
            if Xmin_3dmm <= 0:
                Xmin_3dmm = 0
            if Ymin_3dmm <= 0:
                Ymin_3dmm = 0
            if Xmax_3dmm >= img.shape[1]:
                Xmax_3dmm = img.shape[1]
            if Ymax_3dmm >= img.shape[0]:
                Ymax_3dmm = img.shape[0]

            head_poses = self.hp.get_head_pose(img[int(Ymin_3dmm):int(Ymax_3dmm), int(Xmin_3dmm):int(Xmax_3dmm)])
            
            # Check if head pose is within acceptable thresholds
            if head_poses[0] > self.pose_threshold[0][0] and head_poses[0] < self.pose_threshold[0][1] and \
               head_poses[1] > self.pose_threshold[1][0] and head_poses[1] < self.pose_threshold[1][1] and \
               head_poses[2] > self.pose_threshold[2][0] and head_poses[2] < self.pose_threshold[2][1]:
                loc_dict['bounding_box_p'] = np.array((y1, y2, x1, x2))
            else:
                print('侧脸检测不通过', head_poses)
                loc_dict['bounding_box_p'] = []
        else:
            loc_dict['bounding_box_p'] = []
            
        self.mp_dict[idx] = loc_dict

    def loc_crop_face(self, idx):
        loc_dict = self.mp_dict[idx]
        img = loc_dict['imgs_data']
        dets = self.mp_dict[idx]['bounding_box_p']
        
        # Handle case where no valid face was detected
        if len(dets) == 0 or max(dets) == 0:
            self.no_face.append(idx)
            dets = [0, 100, 0, 100]
            self.mp_dict[idx]['bounding_box_p'] = [0, 0, 0, 0]

        if len(dets) > 0:
            t0 = time.time()
            face_landmarks = self.scrfd_predictor.forward(img[int(dets[0]):int(dets[1]), int(dets[2]):int(dets[3])])[0]
            landmarks = face_landmarks + np.array([dets[2], dets[0]])[np.newaxis, :]
            loc_dict['landmarks'] = landmarks
            
            (xmin, ymin, w, h) = cv2.boundingRect(np.array(landmarks).astype(np.int32))
            x_c = xmin + w / 2.0

            # Define cropping box based on landmarks and aspect ratio
            Xmin = int(x_c - w / self.wh * 0.75)
            Xmax = int(x_c + w / self.wh * 0.75)
            Ymin = int(ymin - w / self.wh * 0.15)
            Ymax = int(ymin + w / self.wh * 1.35)

            # Clamp coordinates
            if Xmin <= 0: Xmin = 0
            if Ymin <= 0: Ymin = 0
            if Xmax >= img.shape[1]: Xmax = img.shape[1]
            if Ymax >= img.shape[0]: Ymax = img.shape[0]

            loc_dict['bounding_box'] = np.array([Ymin, Ymax, Xmin, Xmax])
            
            # Normalize landmarks to the cropped image
            lm_crop = np.zeros(landmarks.shape)
            lm_crop[..., 0] = self.target_size * (landmarks[..., 0] - Xmin) / (Xmax - Xmin)
            lm_crop[..., 1] = self.target_size * (landmarks[..., 1] - Ymin) / (Ymax - Ymin)

            # Crop and resize image
            img_crop = img[Ymin:Ymax, Xmin:Xmax]
            if self.driver_flag:
                img_crop = cv2.cvtColor(cv2.resize(img_crop, (self.target_size, self.target_size), interpolation=cv2.INTER_CUBIC), cv2.COLOR_BGR2RGB)
            else:
                img_crop = cv2.resize(img_crop, (self.target_size, self.target_size), interpolation=cv2.INTER_CUBIC)
            
            loc_dict['crop_lm'] = lm_crop
            loc_dict['crop_img'] = img_crop
            self.mp_dict[idx] = loc_dict

    def smooth_(self):
        max_len = np.array([it for it in self.mp_dict.keys()]).max()
        bbx_smooth = np.zeros((max_len, 4))
        keylist = list(self.mp_dict.keys())
        keylist.sort()
        
        # Fill in missing bounding boxes with the previous one
        for it in keylist:
            if len(self.mp_dict[it]['bounding_box_p']) != 4:
                bbx_smooth[it - 1, :] = bbx_smooth[it - 2, :]
                continue
            bbx_smooth[it - 1, :] = self.mp_dict[it]['bounding_box_p']

        # Apply a simple moving average filter
        conv_core = np.ones((5, 1)) / 5.0
        bbx_smooth2 = signal.convolve2d(bbx_smooth, conv_core, boundary='symm', mode='same')
        
        # Replace original with smoothed if the difference is small
        bbx_smooth_dif = np.where(np.abs(bbx_smooth2 - bbx_smooth).sum(1) > 12)[0]
        bbx_smooth3 = bbx_smooth + 0
        bbx_smooth3[bbx_smooth_dif] = bbx_smooth[bbx_smooth_dif]
        
        bbx_smooth4 = signal.convolve2d(bbx_smooth3, conv_core, boundary='symm', mode='same')
        
        # Update the dictionary with smoothed boxes
        for it in self.mp_dict:
            loc_dict = self.mp_dict[it]
            loc_dict['bounding_box_p'] = bbx_smooth4[it - 1, :]
            self.mp_dict[it] = loc_dict


    def flow(self):
        for idx in self.mp_dict.keys():
            self.loc_detect_face(idx)
        for idx in self.mp_dict.keys():
            self.loc_crop_face(idx)