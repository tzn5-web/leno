package ro.evolauncher.k2401;

/**
 * Pure priority scheduler for ELM Mode 01. RPM + STFT must be read every
 * iteration; coolant is limited to >=2s and LTFT to >=5s. One outstanding
 * PID at a time. No fixed 1ms polling or background telemetry.
 */
final class ObdPollPlan {
  static final int RPM=0,STFT=1,COOLANT=2,LTFT=3;
  private ObdPollPlan(){}
  static int[] next(long now,long lastCoolant,long lastLtft){
    boolean water=lastCoolant==0||now-lastCoolant>=2000L;
    boolean longTrim=lastLtft==0||now-lastLtft>=5000L;
    if(water&&longTrim)return new int[]{RPM,STFT,COOLANT,LTFT};
    if(water)return new int[]{RPM,STFT,COOLANT};
    if(longTrim)return new int[]{RPM,STFT,LTFT};
    return new int[]{RPM,STFT};
  }
  static long minimumGapMs(long responseMs){
    // Responsive ECU => 20ms minimum transport gap; slow ECU => <=80ms.
    return Math.max(20L,Math.min(80L,responseMs/4L));
  }
}
