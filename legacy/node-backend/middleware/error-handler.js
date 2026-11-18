function errorHandler(error, request, response, next) {
  const status = Number.isInteger(error.status) && error.status >= 400 && error.status < 600
    ? error.status
    : 500;
  const isProduction = process.env.NODE_ENV === 'production';
  const message = status === 500 && isProduction
    ? 'Internal server error'
    : error.message || 'Internal server error';

  response.status(status).json({
    message,
  });
}

module.exports = errorHandler;
