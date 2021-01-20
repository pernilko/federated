import tensorflow as tf

from mitbih_model import create_cnn_model

class ModelTest(tf.test.TestCase):
    def test_cnn_model_shape(self):
        """
        Function that tests function for model output shape
        """
        data = tf.random.normal([32, 187, 1])
        model = create_cnn_model()
        logits = model(data)
        self.assertEqual(logits.shape, [32, 5])

if __name__ == "__main__":
    tf.test.main()