from torchvision import transforms
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import imutils
import cv2
import numpy as np

#First process the image
def crop_img(src):
  '''
  This is a modified form of the function from 
  https://www.pyimagesearch.com/2016/04/11/finding-extreme-points-in-contours-with-opencv/
  to use OpenCV to crop an image for this usecase
  '''

  img = cv2.imread(src,1)
  img = cv2.resize(img, (224,224), interpolation=cv2.INTER_CUBIC)
  gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
  gray = cv2.GaussianBlur(gray, (5, 5), 0)

  # threshold the image, then perform a series of erosions +
  # dilations to remove any small regions of noise
  thresh = cv2.threshold(gray, 45, 255, cv2.THRESH_BINARY)[1]
  thresh = cv2.erode(thresh, None, iterations=2)
  thresh = cv2.dilate(thresh, None, iterations=2)

  # find contours in thresholded image, then grab the largest one
  cnts = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
  cnts = imutils.grab_contours(cnts)
  c = max(cnts, key=cv2.contourArea)

  # find the extreme points
  extLeft = tuple(c[c[:, :, 0].argmin()][0])
  extRight = tuple(c[c[:, :, 0].argmax()][0])
  extTop = tuple(c[c[:, :, 1].argmin()][0])
  extBot = tuple(c[c[:, :, 1].argmax()][0])

  # add contour on the image
  img_cnt = cv2.drawContours(img.copy(), [c], -1, (0, 255, 255), 4)

  # add extreme points
  img_pnt = cv2.circle(img_cnt.copy(), extLeft, 8, (0, 0, 255), -1)
  img_pnt = cv2.circle(img_pnt, extRight, 8, (0, 255, 0), -1)
  img_pnt = cv2.circle(img_pnt, extTop, 8, (255, 0, 0), -1)
  img_pnt = cv2.circle(img_pnt, extBot, 8, (255, 255, 0), -1)

  # crop
  ADD_PIXELS = 0
  new_img = img[extTop[1]-ADD_PIXELS:extBot[1]+ADD_PIXELS, extLeft[0]-ADD_PIXELS:extRight[0]+ADD_PIXELS].copy()

  return new_img


#Now we must z-score normalize the picture

#with z-score normalization and resizing to 32,32
def znormalize(img):
  '''
  Z-Score normalizes an image to normalize image intensity.
  '''
  img = cv2.resize(img, (32,32))
  img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
  mean, stdDev = cv2.meanStdDev(img)  
  img = (img-mean)/stdDev
  img = to_tensor(img)
  img = img.unsqueeze(0)
  
  return img

#The Following is the proposed Neural Network Structure as mentioned in 
# https://arxiv.org/ftp/arxiv/papers/1902/1902.06924.pdf

class CAE(nn.Module):
  def __init__(self):
    super(CAE, self).__init__()

    #encoder part

    self.conv1 = nn.Conv2d(32, 64, 3, 2)
    self.conv2 = nn.Conv2d(64, 128, 3, 2)
    self.conv3 = nn.Conv2d(128, 192, 3, 2)
    self.conv4 = nn.Conv2d(192, 64, 4, 1)
    self.conv5 = nn.Conv2d(64, 128, 1, 1)
       
    #decoder part
    self.t_conv1 = nn.ConvTranspose2d(128, 64, 4, 1)
    self.t_conv2 = nn.ConvTranspose2d(64, 64, 3, 2)
    self.t_conv3 = nn.ConvTranspose2d(64, 64, 3, 2)
    self.t_conv4 = nn.ConvTranspose2d(32, 64, 3, 2)

  def forward(self, x):
    x = F.relu(self.conv1(x))
    x = F.relu(self.conv2(x))
    x = F.BatchNorm2d(x)
    x = F.relu(self.conv3(x))
    x = F.batch_norm(x)
    x = F.relu(self.conv4(x))
    x = F.batch_norm(x)
    x = F.relu(self.conv5(x))
    x = F.batch_norm(x)
    x = F.leaky_relu(self.t_conv1(x))
    x = F.batch_norm(x)
    x = F.leaky_relu(self.t_conv2(x))
    x = F.batch_norm(x)
    x = F.leaky_relu(self.t_conv3(x))
    x = F.batch_norm(x)
    x = F.tanh(self.t_conv4(x))

    return x


model = CAE()
criterion = nn.BCELoss()
optimizer = torch.optim.Adam(model.parameters(), lr=1e-5)

#Now we train this architecture
