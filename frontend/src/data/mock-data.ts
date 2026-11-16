export type Role = "student" | "faculty";
export type Mark = { obtained: number; maximum: number };
export type AcademicRecord = { studentId: string; semester: number; subjectName: string; internal1: Mark; internal2: Mark | null; assignment: Mark };
export type Student = { id: string; rollNumber: string; name: string; email: string; department: string; semester: number; attendance: number; prediction: number; stage1: number; status: string; monitoring: string };

export const currentStudent: Student = { id:"stu-rahul", rollNumber:"CS21041", name:"Rahul Sharma", email:"rahul.sharma@campus.edu", department:"Computer Science", semester:7, attendance:87, prediction:72, stage1:64, status:"Below Benchmark", monitoring:"Under Monitoring" };
export const faculty = { id:"fac-1024", employeeId:"FAC1024", name:"Dr. Meera Sharma", email:"meera.sharma@campus.edu", department:"Computer Science" };
export const students: Student[] = [
 currentStudent,
 { id:"stu-priya", rollNumber:"CS21042", name:"Priya Verma", email:"priya.verma@campus.edu", department:"Computer Science", semester:7, attendance:93, prediction:84, stage1:78, status:"On Track", monitoring:"Improved" },
 { id:"stu-aman", rollNumber:"CS21043", name:"Aman Singh", email:"aman.singh@campus.edu", department:"Computer Science", semester:7, attendance:74, prediction:61, stage1:58, status:"Below Benchmark", monitoring:"Contacted" },
 { id:"stu-neha", rollNumber:"CS21044", name:"Neha Gupta", email:"neha.gupta@campus.edu", department:"Computer Science", semester:7, attendance:89, prediction:76, stage1:72, status:"On Track", monitoring:"Not Contacted" },
 { id:"stu-arjun", rollNumber:"CS21045", name:"Arjun Kumar", email:"arjun.kumar@campus.edu", department:"Computer Science", semester:7, attendance:79, prediction:68, stage1:63, status:"Improving", monitoring:"Counselling Done" },
 { id:"stu-kavya", rollNumber:"CS21046", name:"Kavya Iyer", email:"kavya.iyer@campus.edu", department:"Computer Science", semester:7, attendance:91, prediction:81, stage1:76, status:"On Track", monitoring:"Not Contacted" },
 { id:"stu-rohan", rollNumber:"CS21047", name:"Rohan Mehta", email:"rohan.mehta@campus.edu", department:"Computer Science", semester:7, attendance:69, prediction:57, stage1:55, status:"Below Benchmark", monitoring:"Under Monitoring" },
 { id:"stu-sneha", rollNumber:"CS21048", name:"Sneha Reddy", email:"sneha.reddy@campus.edu", department:"Computer Science", semester:7, attendance:85, prediction:74, stage1:70, status:"Improving", monitoring:"Contacted" },
];
export const records: AcademicRecord[] = [
 { studentId:"stu-rahul", semester:7, subjectName:"Computer Networks", internal1:{obtained:18,maximum:30}, internal2:{obtained:26,maximum:40}, assignment:{obtained:8,maximum:10} },
 { studentId:"stu-rahul", semester:7, subjectName:"Database Management Systems", internal1:{obtained:24,maximum:30}, internal2:{obtained:29,maximum:40}, assignment:{obtained:9,maximum:10} },
 { studentId:"stu-rahul", semester:7, subjectName:"Machine Learning", internal1:{obtained:27,maximum:30}, internal2:{obtained:34,maximum:40}, assignment:{obtained:9,maximum:10} },
 { studentId:"stu-rahul", semester:7, subjectName:"Software Engineering", internal1:{obtained:21,maximum:25}, internal2:null, assignment:{obtained:17,maximum:20} },
 { studentId:"stu-rahul", semester:7, subjectName:"Cloud Computing", internal1:{obtained:22,maximum:30}, internal2:{obtained:31,maximum:40}, assignment:{obtained:8,maximum:10} },
];
export const benchmark = 70;
export const target = 80;
export const predictionHistory = [
 { stage:"After Internal 1", value:64, date:"18 Aug 2026" },
 { stage:"After Internal 2", value:72, date:"22 Sep 2026" },
];
export const uploadPreview = [
 { rollNumber:"CS21041", studentName:"Rahul Sharma", subject:"Computer Networks", obtained:26, maximum:40, attendance:87 },
 { rollNumber:"CS21042", studentName:"Priya Verma", subject:"Computer Networks", obtained:35, maximum:40, attendance:93 },
 { rollNumber:"CS21043", studentName:"Aman Singh", subject:"Computer Networks", obtained:24, maximum:40, attendance:74 },
 { rollNumber:"CS21044", studentName:"Neha Gupta", subject:"Database Management Systems", obtained:31, maximum:40, attendance:89 },
];
