require('dotenv').config();

const bcrypt = require('bcryptjs');
const connectDatabase = require('../config/db');
const User = require('../models/user');

const seedPassword = 'Campus@123';

async function seedUsers() {
  await connectDatabase();
  const passwordHash = await bcrypt.hash(seedPassword, 12);

  const users = [
    {
      filter: { rollNumber: 'CS21041' },
      data: {
        name: 'Rahul Sharma',
        email: 'rahul@campusconnect.edu',
        passwordHash,
        role: 'student',
        rollNumber: 'CS21041',
        department: 'Computer Science',
        semester: 7,
      },
    },
    {
      filter: { employeeId: 'FAC1024' },
      data: {
        name: 'Dr. Sharma',
        email: 'faculty@campusconnect.edu',
        passwordHash,
        role: 'faculty',
        employeeId: 'FAC1024',
        department: 'Computer Science',
      },
    },
  ];

  for (const user of users) {
    await User.updateOne(
      user.filter,
      { $setOnInsert: user.data },
      { upsert: true, runValidators: true },
    );
  }

  console.log('Development seed users are ready');
}

seedUsers()
  .catch((error) => {
    console.error(`User seeding failed: ${error.message}`);
    process.exitCode = 1;
  })
  .finally(async () => {
    const mongoose = require('mongoose');
    await mongoose.disconnect();
  });