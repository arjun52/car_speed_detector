import os
import time
from datetime import datetime

import dlib
import imutils
import numpy as np
import cv2
from imutils.video import FPS
from imutils.video import VideoStream
from speed_validator import SpeedValidator
from speed_tracker_handler import SpeedTrackerHandler
from centroid_object_creator import CentroidObjectCreator

# import the necessary packages
from constants import LOG_FILE_NAME, PROTO_TEXT_FILE, MODEL_NAME, FRAME_WIDTH_IN_PIXELS, \
    MAX_DISTANCE_FROM_THE_OBJECT, MAX_NUM_OF_CONSECUTIVE_FRAMES_FOR_ACTION, DISTANCE_OF_CAMERA_FROM_ROAD, \
    MIN_CONFIDENCE, CLASSES, MAX_NUM_OF_FRAMES_FOR_OBJECT_TRACKER, SPEED_ESTIMATION_DICT, POINTS, OPEN_DISPLAY, LIST_OF_SPEED_ZONES
from car_speed_logging import logger
from speed_tracker import SpeedTracker


class SpeedDetector:
    def __init__(self):
        # initialize the frame dimensions (we'll set them as soon as we read
        # the first frame from the video)
        self.H = None
        self.W = None
        self.video_stream = None
        self.net = None
        self.current_time_stamp = None
        self.frame = None
        self.rgb = None
        self.meter_per_pixel = None
       
        # Load Model
        self.load_model()
        # Initialize the camera.
        self.initialize_camera()

        # start the frames per second throughput estimator
        self.fps = FPS().start()
        self.centroid_object_creator = CentroidObjectCreator() 


    def load_model(self):
        """
        Load our serialized model from disk
        """
        logger().info("Loading model name:{}, proto_text:{}.".format(MODEL_NAME, PROTO_TEXT_FILE))
        self.net = cv2.dnn.readNetFromCaffe(PROTO_TEXT_FILE,
                                            MODEL_NAME)
        # Set the target to the MOVIDIUS NCS stick connected via USB
        # Prerequisite: https://docs.openvinotoolkit.org/latest/_docs_install_guides_installing_openvino_raspbian.html
        logger().info("Setting MOVIDIUS NCS stick connected via USB as the target to run the model.")
        self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_MYRIAD)

    def initialize_camera(self):
        """
        Initialize the video stream and allow the camera sensor to warmup.
        """
        logger().info("Warming up Raspberry PI camera connected via the PCB slot.")
        self.video_stream = VideoStream(usePiCamera=True).start()
        time.sleep(2.0)
        # vs = VideoStream(src=0).start()
        
    def grab_next_frame(self):
        """
        1. Grab the next frame from the stream.
        2. store the current timestamp, and store the new date.
        """
        self.frame = self.video_stream.read()
        if self.frame is None:
            return
        
        self.current_time_stamp = datetime.now()
        # resize the frame
        self.frame = imutils.resize(self.frame, width=FRAME_WIDTH_IN_PIXELS)
        self.rgb = cv2.cvtColor(self.frame, cv2.COLOR_BGR2RGB)

    def set_frame_dimensions(self):
        """
        If the frame dimensions are empty, set them.
        """
        # if the frame dimensions are empty, set them
        if not self.W or not self.H:
            (self.H, self.W) = self.frame.shape[:2]
            self.meter_per_pixel = DISTANCE_OF_CAMERA_FROM_ROAD / self.W
    
    def loop_over_streams(self):
        while True:
            self.grab_next_frame()
            # check if the frame is None, if so, break out of the loop
            if self.frame is None:
                break
            self.set_frame_dimensions()
            objects = self.centroid_object_creator.create_centroid_tracker_object(self.H, self.W, self.rgb, self.net, self.frame)
            for speed_tracked_object, objectID, centroid in SpeedTrackerHandler.yield_a_speed_tracker_object(objects):
                SpeedTrackerHandler.compute_speed(self.frame, speed_tracked_object, objectID, centroid, self.current_time_stamp, self.meter_per_pixel)
                SpeedValidator.validate_speed(speed_tracked_object, self.current_time_stamp, self.frame)

            # if the *display* flag is set, then display the current frame
            # to the screen and record if a user presses a key
            if OPEN_DISPLAY:
                cv2.imshow("Car_car_speed_detector_frame", self.frame)
                key = cv2.waitKey(1) & 0xFF

                # if the `q` key is pressed, break from the loop
                if key == ord("q"):
                    break

            # Update the FPS counter
            self.fps.update()

    def clean_up(self):
        # stop the timer and display FPS information
        self.fps.stop()
        logger().info("elapsed time: {:.2f}".format(self.fps.elapsed()))
        logger().info("approx. FPS: {:.2f}".format(self.fps.fps()))

        #Close the log file.
        SpeedValidator.close_log_file()

        # close any open windows
        cv2.destroyAllWindows()

        # clean up
        logger().info("cleaning up...")
        self.video_stream.stop()

    def perform_speed_detection(self):
        while True:
            self.loop_over_streams()
        self.clean_up()


if __name__ == "__main__":
    SpeedDetector().perform_speed_detection()

