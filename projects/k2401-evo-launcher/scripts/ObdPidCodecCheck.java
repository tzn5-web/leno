package ro.evolauncher.k2401;

/** Standalone JVM contract test; no adapter/ECU simulation runs in the APK. */
public final class ObdPidCodecCheck {
  private static void eq(int pid,String response,float expected){
    float value=ObdPidCodec.parse(response,pid);
    if(!Float.isFinite(value)||Math.abs(value-expected)>0.001f)
      throw new AssertionError("PID "+pid+" expected "+expected+" received "+value);
  }
  private static void missing(int pid,String response){
    if(!Float.isNaN(ObdPidCodec.parse(response,pid)))
      throw new AssertionError("Must not display synthetic/stale sensor value for "+response);
  }
  public static void main(String[] args){
    eq(0x06,"0106\r41 06 80\r>",0f);
    eq(0x06,"410600",-100f);
    eq(0x07,"41 07 C0\r>",50f);
    eq(0x0C,"SEARCHING...\r41 0C 1A F8\r>",1726f);
    eq(0x0C,"7E8 04 41 0C 1A F8\r>",1726f);
    eq(0x05,"41 05 7D",85f);
    eq(0x05,"410500",-40f);
    missing(0x0C,"NO DATA\r>");
    missing(0x0C,"010C\rSTOPPED\r>");
    missing(0x0C,"010C\r?");
    missing(0x0C,"41060B");
    missing(0x0C,"410C1A");
    missing(0x07,"UNABLE TO CONNECT");
    missing(0x03,"410305");
    System.out.println("K2401_OBD_MODE01_PARSER=PASS; FOUR_REAL_SENSOR_FORMULAS_AND_NO_DATA_VALIDATED");
  }
}
