# WWW2022 submission 2941

The source code of FENDER.  
The model is developed by Tensorflow 1.12.  
For the tensorflow version > 2.0, please do:  
replace  
import tensorflow as tf  
with  
import tensorflow.compat.v1 as tf  
tf.disable_v2_behavior()  

To train the model and test, go the Model folder and run the following command:  
python Main.py --model_type fender --dataset instacart --gpu_id 0
