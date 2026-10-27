package ro.evolauncher.k2401;

import java.util.Locale;

/** Pure Java decoder for read-only ELM327 Mode 01 replies. No synthetic values. */
final class ObdPidCodec {
  private ObdPidCodec(){}
  static float parse(String raw,int pid){
    if(raw==null||raw.length()>8192)return Float.NaN;
    String wanted=String.format(Locale.US,"41%02X",pid);
    for(String line:raw.toUpperCase(Locale.US).split("[\\r\\n]+")){
      if(line.contains("NO DATA")||line.contains("UNABLE")||
          line.contains("ERROR")||line.contains("STOPPED")||line.contains("BUS INIT"))continue;
      String hex=line.replaceAll("[^0-9A-F]","");
      int at=hex.indexOf(wanted);
      if(at<0)continue;
      int dataAt=at+wanted.length();
      int needed=pid==0x0C?4:2;
      if(dataAt+needed>hex.length())continue;
      try{
        int a=Integer.parseInt(hex.substring(dataAt,dataAt+2),16);
        int b=pid==0x0C?Integer.parseInt(hex.substring(dataAt+2,dataAt+4),16):0;
        float result;
        switch(pid){
          case 0x06:case 0x07:result=(a-128)*100f/128f;break;
          case 0x0C:result=(256*a+b)/4f;break;
          case 0x05:result=a-40;break;
          default:return Float.NaN;
        }
        float low=pid==0x0C?0:pid==0x05?-40:-100;
        float high=pid==0x0C?12000:pid==0x05?170:100;
        if(result>=low&&result<=high)return result;
      }catch(NumberFormatException ignored){}
    }
    return Float.NaN;
  }
}
