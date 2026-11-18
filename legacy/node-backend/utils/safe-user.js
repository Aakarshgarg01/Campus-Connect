function toSafeUser(user) {
  const profile = {
    id: user._id.toString(),
    name: user.name,
    email: user.email,
    role: user.role,
    department: user.department,
  };

  if (user.role === 'student') {
    profile.rollNumber = user.rollNumber;
    profile.semester = user.semester;
  } else if (user.role === 'faculty') {
    profile.employeeId = user.employeeId;
  }

  return profile;
}

module.exports = toSafeUser;