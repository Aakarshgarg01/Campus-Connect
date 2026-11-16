require('dotenv').config();

const cors = require('cors');
const cookieParser = require('cookie-parser');
const express = require('express');
const connectDatabase = require('./config/db');
const errorHandler = require('./middleware/error-handler');
const notFound = require('./middleware/not-found');
const healthRoutes = require('./routes/health');
const authRoutes = require('./routes/auth');
const facultyAcademicRoutes = require('./routes/facultyAcademicRoutes');
const facultyAttendanceRoutes = require('./routes/facultyAttendanceRoutes');
const facultyRoutes = require('./routes/facultyRoutes');
const bulkUploadRoutes = require('./routes/bulkUploadRoutes');
const studentPredictionRoutes = require('./routes/studentPredictionRoutes');
const studentRoutes = require('./routes/studentRoutes');

const app = express();
const port = Number(process.env.PORT) || 5000;
const configuredClientUrls = (process.env.CLIENT_URL || 'http://localhost:5173,http://localhost:8080,http://localhost:8081')
  .split(',')
  .map((url) => url.trim())
  .filter(Boolean);

const isLocalDevelopmentOrigin = (origin) => {
  if (!origin) return true;

  try {
    const { hostname, protocol, port } = new URL(origin);
    const isLocalHost = hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '::1';
    return isLocalHost && (protocol === 'http:' || protocol === 'https:') && (!port || /^\d+$/.test(port));
  } catch {
    return false;
  }
};

app.use(cors({
  origin: (origin, callback) => {
    if (!origin || configuredClientUrls.includes(origin) || isLocalDevelopmentOrigin(origin)) {
      callback(null, true);
      return;
    }

    callback(new Error(`CORS blocked for origin: ${origin}`));
  },
  credentials: true,
}));
app.use(express.json());
app.use(cookieParser());

app.use('/api/health', healthRoutes);
app.use('/api/auth', authRoutes);
app.use('/api/faculty', facultyRoutes);
app.use('/api/faculty/academic/bulk', bulkUploadRoutes);
app.use('/api/faculty/academic', facultyAcademicRoutes);
app.use('/api/faculty/attendance', facultyAttendanceRoutes);
app.use('/api/student/predictions', studentPredictionRoutes);
app.use('/api/student', studentRoutes);
app.use(notFound);
app.use(errorHandler);

async function startServer() {
  await connectDatabase();

  return new Promise((resolve) => {
    const server = app.listen(port, () => {
      console.log(`CampusConnect backend listening on http://localhost:${port}`);
      resolve(server);
    });
  });
}

if (require.main === module) {
  startServer().catch((error) => {
    console.error(`Backend startup failed: ${error.message}`);
    process.exit(1);
  });
}

module.exports = { app, startServer };
