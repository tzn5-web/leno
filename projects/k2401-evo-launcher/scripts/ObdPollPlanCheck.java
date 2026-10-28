package ro.evolauncher.k2401;

import java.util.Arrays;
public final class ObdPollPlanCheck {
  private static void eq(String name,int[] actual,int... wanted){
    if(!Arrays.equals(actual,wanted))throw new AssertionError(name+" => "+Arrays.toString(actual));
    if(actual.length<2||actual[0]!=ObdPollPlan.RPM||actual[1]!=ObdPollPlan.STFT)
      throw new AssertionError("RPM and STFT are mandatory fast priority");
  }
  public static void main(String[] args){
    eq("initial",ObdPollPlan.next(10000,0,0),0,1,2,3);
    eq("fast only",ObdPollPlan.next(10030,10000,10000),0,1);
    eq("coolant due",ObdPollPlan.next(12001,10000,10000),0,1,2);
    eq("ltft due",ObdPollPlan.next(15001,14000,10000),0,1,3);
    eq("both due",ObdPollPlan.next(17001,14000,11000),0,1,2,3);
    eq("ambient initial",ObdPollPlan.next(10000,10000,10000,0),0,1,4);
    eq("ambient not due",ObdPollPlan.next(10030,10000,10000,10000),0,1);
    eq("ambient due",ObdPollPlan.next(25100,25100,25100,10000),0,1,4);
    eq("ambient and others",ObdPollPlan.next(27001,24000,21000,10000),0,1,2,3,4);
    if(ObdPollPlan.minimumGapMs(4)!=20L)throw new AssertionError("sub-1ms busy polling");
    if(ObdPollPlan.minimumGapMs(800)!=80L)throw new AssertionError("slow ECU excessive gap");
    System.out.println("K2401_OBD_FAST_RPM_STFT_PRIORITY=PASS; SLOW_COOLANT_LTFT_AMBIENT_SCHEDULE=PASS");
  }
}
