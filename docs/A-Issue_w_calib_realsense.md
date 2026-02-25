A-Issue with calibration RealSense camera
2/25/2026

Current gui has misalignment between the depth bitmap and the rgb bitmap.

This is intrinsic in the RealSense camera since the cameras are located differently.  It is a known issue and RealSense has libraries to deal with it.

It is complicated by the fact that the two images have different resolutions.

We need a tool to be able to generate the calibration Intrinsic and Extrinsic transforms to make the two images coincide.  (forgive wording if incorrect.)

We need a tool to be able to visualize the effects of those transforms on the images.

It would be nice if there was a tool that helped guide the generation of the image captures to generate the calibration.json files.  Do we need 3?  5? 10 captures?  

One possible visualization tool is the ability to toggle the calibration correction on and off while looking at the images in the gui.