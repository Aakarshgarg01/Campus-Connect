const express = require('express');

const router = express.Router();

router.get('/', (request, response) => {
  response.status(200).json({
    status: 'ok',
    service: 'CampusConnect Backend',
  });
});

module.exports = router;
