const express = require('express');
const router = express.Router();
const User = require('../models/user');

router.get('/', (req, res) => {
  res.render('index', { title: 'Home' });
});

router.get('/users', async (req, res) => {
  const users = await User.findAll();
  res.json(users);
});

module.exports = router;
