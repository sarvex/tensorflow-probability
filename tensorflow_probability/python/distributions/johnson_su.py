# Copyright 2020 The TensorFlow Probability Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ============================================================================
"""Johnson's SU distribution class."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

# Dependency imports
import functools
import numpy as np
import tensorflow.compat.v2 as tf

from tensorflow_probability.python import math
from tensorflow_probability.python.distributions import distribution
from tensorflow_probability.python.internal import assert_util
from tensorflow_probability.python.internal import dtype_util
from tensorflow_probability.python.internal import prefer_static
from tensorflow_probability.python.internal import reparameterization
from tensorflow_probability.python.internal import special_math
from tensorflow_probability.python.internal import tensor_util
from tensorflow_probability.python.util.seed_stream import SeedStream


__all__ = [
    'JohnsonSU',
]


class JohnsonSU(distribution.Distribution):
  """Johnson's SU-distribution.

  This distribution has parameters: shape parameters `gamma` and `delta`,
  location `loc`, and `scale`.

  #### Mathematical details

  The probability density function (pdf) is,

  ```none
  pdf(x; gamma, delta, xi, sigma) = exp(-0.5 (gamma + delta arcsinh(y))**2) / Z
  where,
  y = (x - xi) / sigma
  Z = sigma sqrt(2 pi) sqrt(1 + y**2) / delta
  ```

  where:
  * `loc = xi`,
  * `scale = sigma`, and,
  * `Z` is the normalization constant.

  The JohnsonSU distribution is a member of the [location-scale family](
  https://en.wikipedia.org/wiki/Location-scale_family), i.e., it can be
  constructed as,

  ```none
  X ~ JohnsonSU(gamma, delta, loc=0, scale=1)
  Y = loc + scale * X
  ```

  #### Examples

  Examples of initialization of one or a batch of distributions.

  ```python
  import tensorflow_probability as tfp
  tfd = tfp.distributions

  # Define a single scalar Johnson's SU-distribution.
  single_dist = tfd.JohnsonSU(gamma=-2., delta=2., loc=1.1, scale=1.5)

  # Evaluate the pdf at 1, returning a scalar Tensor.
  single_dist.prob(1.)

  # Define a batch of two scalar valued Johnson SU's.
  # The first has shape parameters 1 and 2, mean 3, and scale 11.
  # The second 4, 5, 6 and 22.
  multi_dist = tfd.JohnsonSU(gamma=[1, 4], delta=[2, 5],
                             loc=[3, 6], scale=[11, 22.])

  # Evaluate the pdf of the first distribution on 0, and the second on 1.5,
  # returning a length two tensor.
  multi_dist.prob([0, 1.5])

  # Get 3 samples, returning a 3 x 2 tensor.
  multi_dist.sample(3)
  ```

  Arguments are broadcast when possible.

  ```python
  # Define a batch of two Johnson's SU distributions.
  # Both have gamma 2, delta 3 and mean 1, but different scales.
  dist = tfd.JohnsonSU(gamma=2, delta=3, loc=1, scale=[11, 22.])

  # Evaluate the pdf of both distributions on the same point, 3.0,
  # returning a length 2 tensor.
  dist.prob(3.0)
  ```

  Compute the gradients of samples w.r.t. the parameters:

  ```python
  gamma = tf.Variable(2.0)
  delta = tf.Variable(3.0)
  loc = tf.Variable(2.0)
  scale = tf.Variable(11.0)
  dist = tfd.JohnsonSU(gamma=gamma, delta=delta, loc=loc, scale=scale)
  with tf.GradientTape() as tape:
    samples = dist.sample(5)  # Shape [5]
    loss = tf.reduce_mean(tf.square(samples))  # Arbitrary loss function
  # Unbiased stochastic gradients of the loss function
  grads = tape.gradient(loss, dist.variables)
  ```

  """

  def __init__(self,
               gamma,
               delta,
               loc,
               scale,
               validate_args=False,
               allow_nan_stats=True,
               name=None):
    """Construct Johnson's SU distributions.

    The distributions have shape parameteres `delta` and `gamma`, mean `loc`,
    and scale `scale`.

    The parameters `delta`, `gamma`, `loc`, and `scale` must be shaped in a way
    that supports broadcasting (e.g. `gamma + delta + loc + scale` is a valid
    operation).

    Args:
      gamma: Floating-point `Tensor`. The shape parameter(s) of the
        distribution(s).
      delta: Floating-point `Tensor`. The shape parameter(s) of the
        distribution(s). `delta` must contain only positive values.
      loc: Floating-point `Tensor`. The mean(s) of the distribution(s).
      scale: Floating-point `Tensor`. The scaling factor(s) for the
        distribution(s). Note that `scale` is not technically the standard
        deviation of this distribution but has semantics more similar to
        standard deviation than variance.
      validate_args: Python `bool`, default `False`. When `True` distribution
        parameters are checked for validity despite possibly degrading runtime
        performance. When `False` invalid inputs may silently render incorrect
        outputs.
      allow_nan_stats: Python `bool`, default `True`. When `True`,
        statistics (e.g., mean, mode, variance) use the value '`NaN`' to
        indicate the result is undefined. When `False`, an exception is raised
        if one or more of the statistic's batch members are undefined.
      name: Python `str` name prefixed to Ops created by this class.

    Raises:
      TypeError: if any of gamma, delta, loc and scale are different dtypes.
    """
    parameters = dict(locals())
    with tf.name_scope(name or 'JohnsonSU') as name:
      dtype = dtype_util.common_dtype([gamma, delta, loc, scale], tf.float32)
      self._gamma = tensor_util.convert_nonref_to_tensor(
          gamma, name='gamma', dtype=dtype)
      self._delta = tensor_util.convert_nonref_to_tensor(
          delta, name='delta', dtype=dtype)
      self._loc = tensor_util.convert_nonref_to_tensor(
          loc, name='loc', dtype=dtype)
      self._scale = tensor_util.convert_nonref_to_tensor(
          scale, name='scale', dtype=dtype)
      dtype_util.assert_same_float_dtype((self._gamma, self._delta,
                                          self._loc, self._scale))
      super(JohnsonSU, self).__init__(
          dtype=dtype,
          reparameterization_type=reparameterization.FULLY_REPARAMETERIZED,
          validate_args=validate_args,
          allow_nan_stats=allow_nan_stats,
          parameters=parameters,
          name=name)

  @staticmethod
  def _param_shapes(sample_shape):
    return dict(
        zip(('gamma', 'delta', 'loc', 'scale'),
            ([tf.convert_to_tensor(sample_shape, dtype=tf.int32)] * 4)))

  @classmethod
  def _params_event_ndims(cls):
    return dict(gamma=0, delta=0, loc=0, scale=0)

  @property
  def gamma(self):
    """Gamma shape parameters in these Johnson's SU distribution(s)."""
    return self._gamma

  @property
  def delta(self):
    """Delta shape parameters in these Johnson's SU distribution(s)."""
    return self._delta

  @property
  def loc(self):
    """Locations of these Johnson's SU distribution(s)."""
    return self._loc

  @property
  def scale(self):
    """Scaling factors of these Johnson's SU distribution(s)."""
    return self._scale

  def _batch_shape_tensor(self, gamma=None, delta=None, loc=None, scale=None):
    return functools.reduce(
        prefer_static.broadcast_shape,
        (prefer_static.shape(self.gamma if gamma is None else gamma),
         prefer_static.shape(self.delta if delta is None else delta),
         prefer_static.shape(self.loc if loc is None else loc),
         prefer_static.shape(self.scale if scale is None else scale)))

  def _batch_shape(self):
    return functools.reduce(
        tf.broadcast_static_shape,
        (self.gamma.shape, self.delta.shape, self.loc.shape, self.scale.shape))

  def _event_shape_tensor(self):
    return tf.constant([], dtype=tf.int32)

  def _event_shape(self):
    return tf.TensorShape([])

  def _sample_n(self, n, seed=None):
    gamma = tf.convert_to_tensor(self.gamma)
    delta = tf.convert_to_tensor(self.delta)
    loc = tf.convert_to_tensor(self.loc)
    scale = tf.convert_to_tensor(self.scale)
    batch_shape = self._batch_shape_tensor(gamma=gamma, delta=delta,
                                           loc=loc, scale=scale)
    shape = tf.concat([[n], batch_shape], axis=0)
    seed = SeedStream(seed, 'johnson_su')

    u = tf.random.uniform(shape, minval=0., maxval=1.,
                          dtype=self.dtype, seed=seed())

    samples = tf.sinh((tf.math.ndtri(u) - gamma) / delta)

    return samples * scale + loc  # Abs(scale) not wanted.

  def _log_prob(self, x):
    gamma = tf.convert_to_tensor(self.gamma)
    delta = tf.convert_to_tensor(self.delta)
    scale = tf.convert_to_tensor(self.scale)
    loc = tf.convert_to_tensor(self.loc)

    y = (x - loc) / scale  # Abs(scale) superfluous.

    log_unnormalized = -0.5 * math.log1psquare(y) - \
      0.5 * tf.square(gamma + delta * tf.math.asinh(y))
    log_normalization = tf.math.log(scale/delta) + 0.5 * np.log(2. * np.pi)

    return log_unnormalized - log_normalization

  def _cdf(self, x):
    gamma = tf.convert_to_tensor(self.gamma)
    delta = tf.convert_to_tensor(self.delta)
    scale = tf.convert_to_tensor(self.scale)
    loc = tf.convert_to_tensor(self.loc)

    y = (x - loc) / scale  # Abs(scale) superfluous.
    return special_math.ndtr(gamma + delta * tf.math.asinh(y))

  def _mean(self):
    gamma = tf.convert_to_tensor(self.gamma)
    delta = tf.convert_to_tensor(self.delta)
    scale = tf.convert_to_tensor(self.scale)
    loc = tf.convert_to_tensor(self.loc)

    gamma = gamma * tf.ones(self._batch_shape_tensor(gamma=gamma),
                            dtype=self.dtype)
    delta = delta * tf.ones(self._batch_shape_tensor(delta=delta),
                            dtype=self.dtype)
    scale = scale * tf.ones(self._batch_shape_tensor(scale=scale),
                            dtype=self.dtype)
    loc = loc * tf.ones(self._batch_shape_tensor(loc=loc), dtype=self.dtype)

    mean = loc - scale * tf.math.exp(0.5 / tf.math.square(delta)) * \
      tf.math.sinh(gamma / delta)
    return mean

  def _variance(self):
    gamma = tf.convert_to_tensor(self.gamma)
    delta = tf.convert_to_tensor(self.delta)
    scale = tf.convert_to_tensor(self.scale)

    gamma = gamma * tf.ones(self._batch_shape_tensor(gamma=gamma),
                            dtype=self.dtype)
    delta = delta * tf.ones(self._batch_shape_tensor(delta=delta),
                            dtype=self.dtype)
    scale = scale * tf.ones(self._batch_shape_tensor(scale=scale),
                            dtype=self.dtype)

    return 0.5 * scale**2 * tf.math.expm1(1./delta**2) * \
        (tf.math.exp(1/delta**2) * tf.math.cosh(2. * gamma / delta) + 1.)

  def _parameter_control_dependencies(self, is_init):
    if is_init:
      try:
        self._batch_shape()
      except ValueError:
        raise ValueError(
            'Arguments must have compatible shapes; '
            'gamma.shape={}, delta.shape={}, loc.shape={}, scale.shape={}.'
            .format(self.gamma.shape, self.delta.shape, self.loc.shape,
                    self.scale.shape))
      # We don't bother checking the shapes in the dynamic case because
      # all member functions access all arguments anyway.

    if not self.validate_args:
      return []
    assertions = []
    if is_init != tensor_util.is_ref(self.delta):
      assertions.append(assert_util.assert_positive(
          self.delta, message='Argument `delta` must be positive.'))
    if is_init != tensor_util.is_ref(self.scale):
      assertions.append(assert_util.assert_positive(
          self.scale, message='Argument `scale` must be positive.'))
    return assertions
