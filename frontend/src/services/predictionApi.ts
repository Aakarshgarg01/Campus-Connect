import { mockDelay } from "./api";
export type Stage1Input={attendancePercentage:number;internal1Performance:number;assignmentPerformance:number};
export type Stage2Input=Stage1Input&{internal2Performance:number};
export const predictionApi={ stage1:(input:Stage1Input)=>mockDelay({stage:"stage1",input,status:"pending"}), stage2:(input:Stage2Input)=>mockDelay({stage:"stage2",input,status:"pending"}), whatIf:(input:Stage2Input)=>mockDelay({currentPrediction:72,simulatedPrediction: input.attendancePercentage>=90 ? 76 : 74}) };
