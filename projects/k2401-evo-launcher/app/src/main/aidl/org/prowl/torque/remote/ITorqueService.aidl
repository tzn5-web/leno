// Torque Pro public plugin interface. Method order MUST match upstream Torque AIDL.
// Reference: https://wiki.torque-bhp.com/view/PluginDocumentation
// Only read-only API calls are invoked by EVO Launcher.
package org.prowl.torque.remote;
interface ITorqueService {
  int getVersion();
  float getValueForPid(long pid, boolean triggersDataRefresh);
  String getDescriptionForPid(long pid);
  String getShortNameForPid(long pid);
  String getUnitForPid(long pid);
  float getMinValueForPid(long pid);
  float getMaxValueForPid(long pid);
  long[] getListOfActivePids();
  long[] getListOfECUSupportedPids();
  long[] getListOfAllPids();
  boolean hasFullPermissions();
  String[] sendCommandGetResponse(String header, String command);
  String getPreferredUnit(String unit);
  boolean setPIDData(String name, String shortName, String unit, float max, float min, float value);
  boolean isConnectedToECU();
  boolean setDebugTestMode(boolean activateTestMode);
  String[] getVehicleProfileInformation();
  int storeInProfile(String key, String value, boolean saveToFileNow);
  String retrieveProfileData(String key);
  int getDataErrorCount();
  double getPIDReadSpeed();
  int getConfiguredSpeed();
  boolean isFileLoggingEnabled();
  boolean isWebLoggingEnabled();
  int getNumberOfLoggedItems();
  long getUpdateTimeForPID(long pid);
  float getScaleForPid(long pid);
  String translate(String originalText);
  boolean sendPIDData(String pluginName, in String[] name, in String[] shortName, in String[] modeAndPID, in String[] equation, in float[] minValue, in float[] maxValue, in String[] units, in String[] header);
  boolean setPIDInformation(String name, String shortName, String unit, float max, float min, float value, String stringValue);
  String[] listAllPIDs();
  String[] listActivePIDs();
  String[] listECUSupportedPIDs();
  float[] getPIDValues(in String[] pidsToRetrieve);
  String[] getPIDInformation(in String[] pidIDs);
  long[] getPIDUpdateTime(in String[] pidIDs);
}
