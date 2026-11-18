const test = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const mongoose = require('mongoose');
const bcrypt = require('bcryptjs');
const { app, startServer } = require('../server');
const User = require('../models/user');
const AcademicRecord = require('../models/AcademicRecord');
const Attendance = require('../models/Attendance');

const MONGO_URI = process.env.MONGO_URI || 'mongodb://127.0.0.1:27017/campusconnect_bulk_upload_test';
process.env.MONGO_URI = MONGO_URI;
process.env.JWT_SECRET = process.env.JWT_SECRET || 'bulk-upload-secret';
process.env.JWT_EXPIRES_IN = process.env.JWT_EXPIRES_IN || '1d';

let server;
let facultyCookie;
let studentCookie;
let facultyUserId;
let studentUserId;

async function login(identifier, password) {
  const response = await fetch('http://localhost:5000/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ identifier, password }),
    credentials: 'include',
  });

  const setCookies = response.headers.getSetCookie ? response.headers.getSetCookie() : [];
  const cookieHeader = setCookies.map((cookie) => cookie.split(';')[0]).join('; ');
  return { response, cookieHeader };
}

async function loginAsFaculty() {
  const result = await login('faculty@campusconnect.edu', 'Campus@123');
  facultyCookie = result.cookieHeader;
  facultyUserId = (await result.response.json()).user.id;
}

async function loginAsStudent() {
  const result = await login('CS21041', 'Campus@123');
  studentCookie = result.cookieHeader;
  const body = await result.response.json();
  studentUserId = body.user.id;
}

async function seedBaseData() {
  await mongoose.connect(MONGO_URI);
  await mongoose.connection.db.dropDatabase().catch(() => {});

  const passwordHash = await bcrypt.hash('Campus@123', 12);

  const faculty = await User.create({
    name: 'Dr. Sharma',
    email: 'faculty@campusconnect.edu',
    passwordHash,
    role: 'faculty',
    employeeId: 'FAC1024',
    department: 'Computer Science',
  });

  const student = await User.create({
    name: 'Rahul Sharma',
    email: 'rahul@campusconnect.edu',
    passwordHash,
    role: 'student',
    rollNumber: 'CS21041',
    department: 'Computer Science',
    semester: 7,
  });

  facultyUserId = faculty._id.toString();
  studentUserId = student._id.toString();
}

function csvBuffer(content) {
  return Buffer.from(content, 'utf8');
}

async function uploadPreview({ cookie, fileName, content, extraBody = {} }) {
  const form = new FormData();
  form.append('file', new Blob([content], { type: 'application/vnd.ms-excel' }), fileName);
  Object.entries(extraBody).forEach(([key, value]) => form.append(key, String(value)));

  return fetch('http://localhost:5000/api/faculty/academic/bulk/preview', {
    method: 'POST',
    headers: { Cookie: cookie },
    body: form,
  });
}

async function confirmUpload(cookie, uploadId) {
  return fetch('http://localhost:5000/api/faculty/academic/bulk/confirm', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Cookie: cookie,
    },
    body: JSON.stringify({ uploadId }),
  });
}

test.before(async () => {
  await seedBaseData();
  server = await startServer();
  await loginAsFaculty();
  await loginAsStudent();
});

test.after(async () => {
  await mongoose.disconnect();
  await new Promise((resolve, reject) => {
    server.close((error) => (error ? reject(error) : resolve()));
  });
});

test('A. valid CSV preview succeeds', async () => {
  const csv = [
    'Roll No,Student,Semester,Subject,Internal 1 Obtained,Internal 1 Maximum,Internal 2 Obtained,Internal 2 Maximum,Assignment Obtained,Assignment Maximum,Attendance',
    'CS21041,Rahul Sharma,7,Data Structures,32,40,35,40,8,10,85',
    'CS21041,Rahul Sharma,7,Operating Systems,30,40,, ,8,10,85',
  ].join('\n');

  const response = await uploadPreview({ cookie: facultyCookie, fileName: 'records.csv', content: csv });
  const payload = await response.json();

  assert.equal(response.status, 200);
  assert.equal(payload.valid, true);
  assert.equal(payload.preview.length, 2);
  assert.equal(payload.summary.validRows, 2);
  assert.equal(payload.summary.errorRows, 0);
});

test('B. valid XLSX preview succeeds', async () => {
  const workbook = {
    SheetNames: ['Sheet1'],
    Sheets: {
      Sheet1: {
        '!ref': 'A1:K2',
        A1: { t: 's', v: 'Roll No' },
        B1: { t: 's', v: 'Student' },
        C1: { t: 's', v: 'Semester' },
        D1: { t: 's', v: 'Subject' },
        E1: { t: 's', v: 'Internal 1 Obtained' },
        F1: { t: 's', v: 'Internal 1 Maximum' },
        G1: { t: 's', v: 'Internal 2 Obtained' },
        H1: { t: 's', v: 'Internal 2 Maximum' },
        I1: { t: 's', v: 'Assignment Obtained' },
        J1: { t: 's', v: 'Assignment Maximum' },
        K1: { t: 's', v: 'Attendance' },
        A2: { t: 's', v: 'CS21041' },
        B2: { t: 's', v: 'Rahul Sharma' },
        C2: { t: 'n', v: 7 },
        D2: { t: 's', v: 'DBMS' },
        E2: { t: 'n', v: 34 },
        F2: { t: 'n', v: 40 },
        G2: { t: 'n', v: 36 },
        H2: { t: 'n', v: 40 },
        I2: { t: 'n', v: 9 },
        J2: { t: 'n', v: 10 },
        K2: { t: 'n', v: 87 },
      },
    },
  };

  const buffer = require('xlsx').write(workbook, { type: 'buffer', bookType: 'xlsx' });
  const response = await uploadPreview({ cookie: facultyCookie, fileName: 'records.xlsx', content: buffer });
  const payload = await response.json();

  assert.equal(response.status, 200);
  assert.equal(payload.valid, true);
  assert.equal(payload.preview.length, 1);
});

test('C. invalid extension rejects', async () => {
  const response = await uploadPreview({ cookie: facultyCookie, fileName: 'records.txt', content: 'bad' });
  const payload = await response.json();

  assert.equal(response.status, 400);
  assert.equal(payload.valid, false);
});

test('D. empty file rejects', async () => {
  const response = await uploadPreview({ cookie: facultyCookie, fileName: 'empty.csv', content: '' });
  const payload = await response.json();

  assert.equal(response.status, 400);
  assert.equal(payload.valid, false);
  assert.match(payload.errors[0].message, /empty|unreadable/i);
});

test('E. missing required columns rejects', async () => {
  const csv = 'Roll No,Student,Subject,Attendance\nCS21041,Rahul Sharma,Data Structures,85';
  const response = await uploadPreview({ cookie: facultyCookie, fileName: 'missing.csv', content: csv });
  const payload = await response.json();

  assert.equal(response.status, 400);
  assert.equal(payload.valid, false);
});

test('F. unknown roll number validation error', async () => {
  const csv = [
    'Roll No,Student,Semester,Subject,Internal 1 Obtained,Internal 1 Maximum,Assignment Obtained,Assignment Maximum,Attendance',
    'CS99999,Unknown Student,7,Data Structures,30,40,8,10,85',
  ].join('\n');

  const response = await uploadPreview({ cookie: facultyCookie, fileName: 'unknown.csv', content: csv });
  const payload = await response.json();

  assert.equal(response.status, 400);
  assert.equal(payload.valid, false);
  assert.ok(payload.errors.some((error) => error.message.includes('CS99999')));
});

test('G. student name mismatch validation error', async () => {
  const csv = [
    'Roll No,Student,Semester,Subject,Internal 1 Obtained,Internal 1 Maximum,Assignment Obtained,Assignment Maximum,Attendance',
    'CS21041,Wrong Name,7,Data Structures,30,40,8,10,85',
  ].join('\n');

  const response = await uploadPreview({ cookie: facultyCookie, fileName: 'name-mismatch.csv', content: csv });
  const payload = await response.json();

  assert.equal(response.status, 400);
  assert.equal(payload.valid, false);
  assert.ok(payload.errors.some((error) => error.field.includes('Student')));
});

test('H. obtained > maximum validation error', async () => {
  const csv = [
    'Roll No,Student,Semester,Subject,Internal 1 Obtained,Internal 1 Maximum,Assignment Obtained,Assignment Maximum,Attendance',
    'CS21041,Rahul Sharma,7,Data Structures,45,40,8,10,85',
  ].join('\n');

  const response = await uploadPreview({ cookie: facultyCookie, fileName: 'exceeds.csv', content: csv });
  const payload = await response.json();

  assert.equal(response.status, 400);
  assert.equal(payload.valid, false);
});

test('I. negative marks validation error', async () => {
  const csv = [
    'Roll No,Student,Semester,Subject,Internal 1 Obtained,Internal 1 Maximum,Assignment Obtained,Assignment Maximum,Attendance',
    'CS21041,Rahul Sharma,7,Data Structures,-1,40,8,10,85',
  ].join('\n');

  const response = await uploadPreview({ cookie: facultyCookie, fileName: 'negative.csv', content: csv });
  const payload = await response.json();

  assert.equal(response.status, 400);
  assert.equal(payload.valid, false);
});

test('J/K. invalid attendance values reject', async () => {
  const csvHigh = [
    'Roll No,Student,Semester,Subject,Internal 1 Obtained,Internal 1 Maximum,Assignment Obtained,Assignment Maximum,Attendance',
    'CS21041,Rahul Sharma,7,Data Structures,30,40,8,10,101',
  ].join('\n');
  const responseHigh = await uploadPreview({ cookie: facultyCookie, fileName: 'attendance-high.csv', content: csvHigh });
  const payloadHigh = await responseHigh.json();

  assert.equal(responseHigh.status, 400);
  assert.equal(payloadHigh.valid, false);

  const csvLow = [
    'Roll No,Student,Semester,Subject,Internal 1 Obtained,Internal 1 Maximum,Assignment Obtained,Assignment Maximum,Attendance',
    'CS21041,Rahul Sharma,7,Data Structures,30,40,8,10,-5',
  ].join('\n');
  const responseLow = await uploadPreview({ cookie: facultyCookie, fileName: 'attendance-low.csv', content: csvLow });
  const payloadLow = await responseLow.json();

  assert.equal(responseLow.status, 400);
  assert.equal(payloadLow.valid, false);
});

test('L. missing Internal 2 maximum when Internal 2 obtained exists rejects', async () => {
  const csv = [
    'Roll No,Student,Semester,Subject,Internal 1 Obtained,Internal 1 Maximum,Internal 2 Obtained,Assignment Obtained,Assignment Maximum,Attendance',
    'CS21041,Rahul Sharma,7,Data Structures,30,40,28,8,10,85',
  ].join('\n');

  const response = await uploadPreview({ cookie: facultyCookie, fileName: 'internal2-missing-max.csv', content: csv });
  const payload = await response.json();

  assert.equal(response.status, 400);
  assert.equal(payload.valid, false);
});

test('M. duplicate student+semester+subject in one upload rejects', async () => {
  const csv = [
    'Roll No,Student,Semester,Subject,Internal 1 Obtained,Internal 1 Maximum,Assignment Obtained,Assignment Maximum,Attendance',
    'CS21041,Rahul Sharma,7,Data Structures,30,40,8,10,85',
    'CS21041,Rahul Sharma,7,Data Structures,35,40,9,10,85',
  ].join('\n');

  const response = await uploadPreview({ cookie: facultyCookie, fileName: 'duplicate.csv', content: csv });
  const payload = await response.json();

  assert.equal(response.status, 400);
  assert.equal(payload.valid, false);
  assert.ok(payload.errors.some((error) => error.message.includes('Duplicate')));
});

test('N. conflicting attendance values reject', async () => {
  const csv = [
    'Roll No,Student,Semester,Subject,Internal 1 Obtained,Internal 1 Maximum,Assignment Obtained,Assignment Maximum,Attendance',
    'CS21041,Rahul Sharma,7,Data Structures,30,40,8,10,85',
    'CS21041,Rahul Sharma,7,Operating Systems,28,40,8,10,90',
  ].join('\n');

  const response = await uploadPreview({ cookie: facultyCookie, fileName: 'conflict.csv', content: csv });
  const payload = await response.json();

  assert.equal(response.status, 400);
  assert.equal(payload.valid, false);
  assert.ok(payload.errors.some((error) => error.message.includes('Conflicting')));
});

test('O. preview does not write records', async () => {
  const beforeRecordCount = await AcademicRecord.countDocuments();
  const beforeAttendanceCount = await Attendance.countDocuments();

  const csv = [
    'Roll No,Student,Semester,Subject,Internal 1 Obtained,Internal 1 Maximum,Assignment Obtained,Assignment Maximum,Attendance',
    'CS21041,Rahul Sharma,7,Algorithms,31,40,8,10,86',
  ].join('\n');

  const response = await uploadPreview({ cookie: facultyCookie, fileName: 'preview-only.csv', content: csv });
  const payload = await response.json();

  assert.equal(response.status, 200);
  assert.equal(payload.valid, true);
  assert.equal(await AcademicRecord.countDocuments(), beforeRecordCount);
  assert.equal(await Attendance.countDocuments(), beforeAttendanceCount);
});

test('P. confirm valid upload creates records', async () => {
  const csv = [
    'Roll No,Student,Semester,Subject,Internal 1 Obtained,Internal 1 Maximum,Assignment Obtained,Assignment Maximum,Attendance',
    'CS21041,Rahul Sharma,7,Algorithms,31,40,8,10,86',
  ].join('\n');

  const previewResponse = await uploadPreview({ cookie: facultyCookie, fileName: 'confirm.csv', content: csv });
  const previewPayload = await previewResponse.json();
  const confirmResponse = await confirmUpload(facultyCookie, previewPayload.uploadId);
  const confirmPayload = await confirmResponse.json();

  assert.equal(confirmResponse.status, 200);
  assert.equal(confirmPayload.summary.rowsProcessed, 1);

  const record = await AcademicRecord.findOne({ studentId: studentUserId, semester: 7, subjectName: 'Algorithms' }).lean();
  assert.ok(record);
  assert.equal(record.internal1.obtained, 31);
  assert.equal(record.assignment.obtained, 8);

  const attendance = await Attendance.findOne({ studentId: studentUserId, semester: 7 }).lean();
  assert.ok(attendance);
  assert.equal(attendance.attendancePercentage, 86);
});

test('Q. confirm same academic records again updates rather than duplicates', async () => {
  const csv = [
    'Roll No,Student,Semester,Subject,Internal 1 Obtained,Internal 1 Maximum,Assignment Obtained,Assignment Maximum,Attendance',
    'CS21041,Rahul Sharma,7,Algorithms,34,40,9,10,88',
  ].join('\n');

  const previewResponse = await uploadPreview({ cookie: facultyCookie, fileName: 'update.csv', content: csv });
  const previewPayload = await previewResponse.json();
  const confirmResponse = await confirmUpload(facultyCookie, previewPayload.uploadId);
  const confirmPayload = await confirmResponse.json();

  assert.equal(confirmResponse.status, 200);
  const count = await AcademicRecord.countDocuments({ studentId: studentUserId, semester: 7, subjectName: 'Algorithms' });
  assert.equal(count, 1);
  assert.equal(confirmPayload.summary.academicRecordsUpdated, 1);

  const record = await AcademicRecord.findOne({ studentId: studentUserId, semester: 7, subjectName: 'Algorithms' }).lean();
  assert.equal(record.internal1.obtained, 34);
  assert.equal(record.assignment.obtained, 9);
  assert.equal((await Attendance.findOne({ studentId: studentUserId, semester: 7 }).lean()).attendancePercentage, 88);
});

test('R/S. upload Internal 2 later preserves Internal 1 and assignment', async () => {
  const firstCsv = [
    'Roll No,Student,Semester,Subject,Internal 1 Obtained,Internal 1 Maximum,Assignment Obtained,Assignment Maximum,Attendance',
    'CS21041,Rahul Sharma,7,Theory of Computation,30,40,7,10,84',
  ].join('\n');

  const firstPreview = await uploadPreview({ cookie: facultyCookie, fileName: 'toc-first.csv', content: firstCsv });
  await confirmUpload(facultyCookie, (await firstPreview.json()).uploadId);

  const secondCsv = [
    'Roll No,Student,Semester,Subject,Internal 1 Obtained,Internal 1 Maximum,Internal 2 Obtained,Internal 2 Maximum,Assignment Obtained,Assignment Maximum,Attendance',
    'CS21041,Rahul Sharma,7,Theory of Computation,30,40,35,40,7,10,84',
  ].join('\n');

  const secondPreview = await uploadPreview({ cookie: facultyCookie, fileName: 'toc-second.csv', content: secondCsv });
  const secondUploadId = (await secondPreview.json()).uploadId;
  const secondConfirm = await confirmUpload(facultyCookie, secondUploadId);
  assert.equal(secondConfirm.status, 200);

  const record = await AcademicRecord.findOne({ studentId: studentUserId, semester: 7, subjectName: 'Theory of Computation' }).lean();
  assert.equal(record.internal1.obtained, 30);
  assert.equal(record.internal2.obtained, 35);
  assert.equal(record.assignment.obtained, 7);
});

test('T. existing attendance is updated rather than duplicated', async () => {
  const before = await Attendance.countDocuments({ studentId: studentUserId, semester: 7 });
  const csv = [
    'Roll No,Student,Semester,Subject,Internal 1 Obtained,Internal 1 Maximum,Assignment Obtained,Assignment Maximum,Attendance',
    'CS21041,Rahul Sharma,7,Operating Systems,29,40,8,10,89',
  ].join('\n');

  const preview = await uploadPreview({ cookie: facultyCookie, fileName: 'attendance-update.csv', content: csv });
  const uploadId = (await preview.json()).uploadId;
  const confirm = await confirmUpload(facultyCookie, uploadId);
  const after = await Attendance.countDocuments({ studentId: studentUserId, semester: 7 });

  assert.equal(confirm.status, 200);
  assert.equal(before, after);
  assert.equal((await Attendance.findOne({ studentId: studentUserId, semester: 7 }).lean()).attendancePercentage, 89);
});

test('U. invalid upload writes nothing', async () => {
  const csv = [
    'Roll No,Student,Semester,Subject,Internal 1 Obtained,Internal 1 Maximum,Assignment Obtained,Assignment Maximum,Attendance',
    'CS21041,Rahul Sharma,7,Invalid Subject,45,40,8,10,85',
  ].join('\n');

  const response = await uploadPreview({ cookie: facultyCookie, fileName: 'invalid-write.csv', content: csv });
  assert.equal(response.status, 400);
  assert.equal(await AcademicRecord.countDocuments({ subjectName: 'Invalid Subject' }), 0);
});

test('V. student upload rejects 403', async () => {
  const response = await uploadPreview({ cookie: studentCookie, fileName: 'student.csv', content: 'Roll No,Student,Semester,Subject,Internal 1 Obtained,Internal 1 Maximum,Assignment Obtained,Assignment Maximum,Attendance\nCS21041,Rahul Sharma,7,Data Structures,30,40,8,10,85' });
  assert.equal(response.status, 403);
});

test('W. unauthenticated upload rejects 401', async () => {
  const response = await fetch('http://localhost:5000/api/faculty/academic/bulk/preview', {
    method: 'POST',
    body: new FormData(),
  });

  assert.equal(response.status, 401);
});

test('X. unknown student is never created automatically', async () => {
  const csv = [
    'Roll No,Student,Semester,Subject,Internal 1 Obtained,Internal 1 Maximum,Assignment Obtained,Assignment Maximum,Attendance',
    'CS99999,Unknown,7,Data Structures,30,40,8,10,85',
  ].join('\n');

  const response = await uploadPreview({ cookie: facultyCookie, fileName: 'unknown-create.csv', content: csv });
  const payload = await response.json();
  assert.equal(response.status, 400);
  assert.equal(await User.countDocuments({ rollNumber: 'CS99999' }), 0);
  assert.ok(payload.errors.some((error) => error.message.includes('CS99999')));
});

test('AD. temporary upload references expire or reject after expiration', async () => {
  const csv = [
    'Roll No,Student,Semester,Subject,Internal 1 Obtained,Internal 1 Maximum,Assignment Obtained,Assignment Maximum,Attendance',
    'CS21041,Rahul Sharma,7,Data Structures,30,40,8,10,85',
  ].join('\n');

  const previewResponse = await uploadPreview({ cookie: facultyCookie, fileName: 'expire.csv', content: csv });
  const previewPayload = await previewResponse.json();

  const storage = require('../services/bulkUploadService');
  const uploadId = previewPayload.uploadId;
  const upload = storage.TEMP_UPLOADS.get(uploadId);
  upload.expiresAt = Date.now() - 1;

  const confirmResponse = await confirmUpload(facultyCookie, uploadId);
  const confirmPayload = await confirmResponse.json();

  assert.equal(confirmResponse.status, 400);
  assert.equal(confirmPayload.message.includes('expired') || confirmPayload.message.includes('invalid'), true);
});

test('AE. confirm cannot be reused after successful confirmation', async () => {
  const csv = [
    'Roll No,Student,Semester,Subject,Internal 1 Obtained,Internal 1 Maximum,Assignment Obtained,Assignment Maximum,Attendance',
    'CS21041,Rahul Sharma,7,Reuse Check,30,40,8,10,85',
  ].join('\n');

  const previewResponse = await uploadPreview({ cookie: facultyCookie, fileName: 'reuse.csv', content: csv });
  const uploadId = (await previewResponse.json()).uploadId;

  await confirmUpload(facultyCookie, uploadId);
  const reused = await confirmUpload(facultyCookie, uploadId);
  const reusedPayload = await reused.json();

  assert.equal(reused.status, 400);
  assert.ok(reusedPayload.message.includes('used') || reusedPayload.message.includes('invalid'));
});

test('AF. confirm request cannot modify validated data by sending different academic values', async () => {
  const previewCsv = [
    'Roll No,Student,Semester,Subject,Internal 1 Obtained,Internal 1 Maximum,Assignment Obtained,Assignment Maximum,Attendance',
    'CS21041,Rahul Sharma,7,Protected Data,30,40,8,10,85',
  ].join('\n');

  const previewResponse = await uploadPreview({ cookie: facultyCookie, fileName: 'protected.csv', content: previewCsv });
  const uploadId = (await previewResponse.json()).uploadId;

  const tampered = await fetch('http://localhost:5000/api/faculty/academic/bulk/confirm', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Cookie: facultyCookie,
    },
    body: JSON.stringify({
      uploadId,
      rows: [{ rollNumber: 'CS21041', semester: 7, subject: 'Protected Data', internal1: { obtained: 99, maximum: 100 }, assignment: { obtained: 9, maximum: 10 }, attendance: 100 }],
    }),
  });

  const tamperedPayload = await tampered.json();
  assert.equal(tampered.status, 200);
  const record = await AcademicRecord.findOne({ studentId: studentUserId, semester: 7, subjectName: 'Protected Data' }).lean();
  assert.equal(record.internal1.obtained, 30);
  assert.equal(record.assignment.obtained, 8);
});
