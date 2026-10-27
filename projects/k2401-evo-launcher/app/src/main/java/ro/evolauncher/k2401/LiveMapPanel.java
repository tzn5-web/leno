package ro.evolauncher.k2401;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.location.Address;
import android.location.Geocoder;
import android.location.Location;
import android.location.LocationListener;
import android.location.LocationManager;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;
import com.google.android.gms.common.ConnectionResult;
import com.google.android.gms.common.GoogleApiAvailability;
import com.google.android.gms.maps.CameraUpdateFactory;
import com.google.android.gms.maps.GoogleMap;
import com.google.android.gms.maps.MapView;
import com.google.android.gms.maps.model.LatLng;
import com.google.android.gms.maps.model.MarkerOptions;
import org.osmdroid.config.Configuration;
import org.osmdroid.tileprovider.tilesource.TileSourceFactory;
import org.osmdroid.util.GeoPoint;
import org.osmdroid.views.overlay.Marker;
import java.util.List;
import java.util.Locale;

/** Interactive map genuinely hosted in the Home pane. NO external JS/CDN, NO external Maps Activity.
 * The Maps SDK path is used with a valid configured key; otherwise osmdroid draws OSM tiles natively.
 * This is an embedded map/search/position, NOT unlicensed Google turn-by-turn navigation.
 */
final class LiveMapPanel extends FrameLayout implements LocationListener {
  private final Activity activity;
  private MapView googleView;
  private GoogleMap googleMap;
  private org.osmdroid.views.MapView osm;
  private Marker osmPosition;
  private Marker gpsMarker;
  private com.google.android.gms.maps.model.Marker googleSearchMarker;
  private LocationManager locations;
  private boolean mapStarted, mapResumed, active, hasFix, followLocation=true;
  private boolean initialZoomSet;
  private final boolean usingGoogle;
  private final TextView status;
  private final GeoPoint initialCenter = new GeoPoint(45.94,24.97); // Neutral initial view, NOT a fake GPS fix.
  private GeoPoint selectedDestination;

  LiveMapPanel(Activity host) {
    super(host);activity=host;
    setBackgroundColor(0xff182332);
    usingGoogle=BuildConfig.GOOGLE_MAPS_CONFIGURED &&
      GoogleApiAvailability.getInstance().isGooglePlayServicesAvailable(host)==ConnectionResult.SUCCESS;
    if(usingGoogle) {
      googleView=new MapView(host);
      addView(googleView,new FrameLayout.LayoutParams(-1,-1));
      googleView.onCreate(null);
      googleView.getMapAsync(map->{
        googleMap=map;
        map.getUiSettings().setZoomControlsEnabled(false);
        map.getUiSettings().setCompassEnabled(true);
        map.setOnCameraMoveStartedListener(reason->{if(reason==GoogleMap.OnCameraMoveStartedListener.REASON_GESTURE)followLocation=false;});
        map.moveCamera(CameraUpdateFactory.newLatLngZoom(new LatLng(initialCenter.getLatitude(),initialCenter.getLongitude()),6f));
        if(hasLocationPermission())try{map.setMyLocationEnabled(true);}catch(SecurityException ignored){}
        Location l=lastLocation();if(l!=null)moveTo(l);
      });
    }else{
      // Native tile renderer: no remote scripts or browser dependencies.
      Configuration.getInstance().setUserAgentValue(host.getPackageName()+"/1.0 (in-car interactive map)");
      Configuration.getInstance().setOsmdroidBasePath(host.getCacheDir());
      Configuration.getInstance().setOsmdroidTileCache(new java.io.File(host.getCacheDir(),"osm-tiles"));
      osm=new org.osmdroid.views.MapView(host);
      osm.setTileSource(TileSourceFactory.MAPNIK);
      osm.setMultiTouchControls(true);
      osm.setBuiltInZoomControls(false);
      osm.getController().setZoom(7.0);
      osm.getController().setCenter(initialCenter);
      osm.setTilesScaledToDpi(true);
      addView(osm,new FrameLayout.LayoutParams(-1,-1));
      osm.setOnTouchListener((v,event)->{if(event.getAction()==android.view.MotionEvent.ACTION_DOWN)followLocation=false;return false;});
    }

    status=new TextView(host);
    status.setText(usingGoogle?"GOOGLE MAPS • HARTĂ INTEGRATĂ":"OpenStreetMap • HARTĂ INTEGRATĂ");
    status.setTextSize(11);status.setTextColor(Color.WHITE);
    status.setBackgroundColor(0xe5101722);status.setPadding(dp(8),dp(6),dp(8),dp(6));
    FrameLayout.LayoutParams statusParams=new FrameLayout.LayoutParams(-2,-2,Gravity.TOP|Gravity.RIGHT);
    statusParams.setMargins(0,dp(8),dp(8),0);addView(status,statusParams);
    LinearLayout controls=new LinearLayout(host);controls.setOrientation(LinearLayout.HORIZONTAL);
    controls.setGravity(Gravity.CENTER);controls.setBackgroundColor(0xdd121a24);
    FrameLayout.LayoutParams actionsParams=new FrameLayout.LayoutParams(-2,dp(48),Gravity.BOTTOM|Gravity.CENTER_HORIZONTAL);
    actionsParams.bottomMargin=dp(9);addView(controls,actionsParams);
    Button locate=button("LOCATIA MEA");
    Button search=button("CAUTA LOC");
    Button plus=button("+");
    Button minus=button("−");
    controls.addView(locate);controls.addView(search);controls.addView(plus);controls.addView(minus);
    locate.setOnClickListener(v->{
      followLocation=true;
      Location l=lastLocation();
      if(l!=null){moveTo(l,true);}
      else{
        status.setText("GPS INDISPONIBIL • VERIFICA LOCATIA");
        Toast.makeText(activity,"Activează GPS și permite accesul la locație.",Toast.LENGTH_LONG).show();
      }
    });
    search.setOnClickListener(v->searchInsidePanel());
    plus.setOnClickListener(v->zoom(1));minus.setOnClickListener(v->zoom(-1));
  }
  private int dp(int x){return (int)(x*getResources().getDisplayMetrics().density+0.5f);}
  private Button button(String label) {
    Button b=new Button(activity);b.setText(label);b.setAllCaps(false);
    b.setTextSize(10);b.setTextColor(Color.WHITE);
    b.setMinWidth(0);b.setMinimumWidth(0);b.setPadding(dp(6),0,dp(6),0);
    b.setBackgroundTintList(android.content.res.ColorStateList.valueOf(0xff862438));
    return b;
  }
  private void zoom(int direction) {
    if(osm!=null){double z=osm.getZoomLevelDouble();osm.getController().setZoom(Math.max(3,Math.min(19,z+direction)));}
    if(googleMap!=null)googleMap.animateCamera(direction>0?CameraUpdateFactory.zoomIn():CameraUpdateFactory.zoomOut());
  }
  private volatile long lastRemoteSearchMs=0L;
  private void searchInsidePanel() {
    EditText edit=new EditText(activity);
    edit.setSingleLine(true);edit.setHint("Oraș sau adresă");
    edit.setInputType(android.text.InputType.TYPE_CLASS_TEXT);
    new AlertDialog.Builder(activity).setTitle("Caută pe harta integrată")
      .setView(edit).setNegativeButton("Anulează",null).setPositiveButton("Caută",(d,w)->{
        String query=edit.getText().toString().trim();
        if(query.length()<3)return;
        status.setText("CĂUTARE: "+query);
        new Thread(()->{
          try{
            double lat=Double.NaN,lon=Double.NaN;
            // Android 10 OEM firmware frequently lacks a Geocoder backend
            // despite having GPS and working OSM tiles. Try it once, then use
            // Nominatim for one user-triggered search (never autocomplete).
            if(Geocoder.isPresent()){
              try{
                List<Address> result=new Geocoder(activity,Locale.getDefault()).getFromLocationName(query,1);
                if(result!=null&&!result.isEmpty()){
                  lat=result.get(0).getLatitude();lon=result.get(0).getLongitude();
                }
              }catch(Exception ignored){/* Android OEM geocoder missing/broken */}
            }
            if(!Double.isFinite(lat)||!Double.isFinite(lon)){
              // OSMF usage policy: max 1 request/sec, identifying User-Agent,
              // attribution, no prefetch/autocomplete, explicit human query.
              long now=android.os.SystemClock.elapsedRealtime();
              long wait=Math.max(0L,1100L-(now-lastRemoteSearchMs));
              if(wait>0)Thread.sleep(wait);
              lastRemoteSearchMs=android.os.SystemClock.elapsedRealtime();
              String uri="https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&q="+
                java.net.URLEncoder.encode(query,"UTF-8");
              java.net.HttpURLConnection connection=(java.net.HttpURLConnection)
                new java.net.URL(uri).openConnection();
              try{
                connection.setRequestMethod("GET");
                connection.setRequestProperty("User-Agent",
                  "K2401-EVO-Launcher/1.2 (https://github.com/tzn5-web/leno)");
                connection.setRequestProperty("Accept-Language","ro,en");
                connection.setRequestProperty("Accept","application/json");
                connection.setConnectTimeout(8000);connection.setReadTimeout(8000);
                int http=connection.getResponseCode();
                if(http!=200)throw new java.io.IOException("HTTP "+http);
                try(java.io.InputStream stream=connection.getInputStream()){
                  java.io.ByteArrayOutputStream buffer=new java.io.ByteArrayOutputStream();
                  byte[] tmp=new byte[1024];int n;
                  while((n=stream.read(tmp))!=-1){
                    if(buffer.size()+n>65536)throw new java.io.IOException("Răspuns prea mare");
                    buffer.write(tmp,0,n);
                  }
                  org.json.JSONArray list=new org.json.JSONArray(buffer.toString("UTF-8"));
                  if(list.length()==0)throw new java.io.IOException("Nu am găsit destinația");
                  org.json.JSONObject item=list.getJSONObject(0);
                  lat=Double.parseDouble(item.getString("lat"));
                  lon=Double.parseDouble(item.getString("lon"));
                }
              }finally{connection.disconnect();}
            }
            if(!Double.isFinite(lat)||!Double.isFinite(lon)||Math.abs(lat)>90||Math.abs(lon)>180)
              throw new java.io.IOException("Coordonate invalide");
            final double resultLat=lat,resultLon=lon;
            activity.runOnUiThread(()->{
              selectedDestination=new GeoPoint(resultLat,resultLon);followLocation=false;
              if(osm!=null){
                if(osmPosition!=null)osm.getOverlays().remove(osmPosition);
                Marker marker=new Marker(osm);marker.setPosition(selectedDestination);
                marker.setTitle(query);osmPosition=marker;osm.getOverlays().add(marker);
                osm.getController().setZoom(15.0);osm.getController().animateTo(selectedDestination);osm.invalidate();
              }
              if(googleMap!=null){
                if(googleSearchMarker!=null)googleSearchMarker.remove();
                googleSearchMarker=googleMap.addMarker(new MarkerOptions().position(new LatLng(resultLat,resultLon)).title(query));
                googleMap.animateCamera(CameraUpdateFactory.newLatLngZoom(new LatLng(resultLat,resultLon),15f));
              }
              status.setText("LOC GĂSIT • "+query);
            });
          }catch(Exception e){activity.runOnUiThread(()->{
            status.setText("CĂUTARE INDISPONIBILĂ • VERIFICĂ INTERNETUL");
            Toast.makeText(activity,"Căutarea adresei a eșuat: "+e.getMessage(),Toast.LENGTH_LONG).show();
          });}
        },"k2401-osm-geocode").start();
      }).show();
  }
  private boolean hasLocationPermission(){
    return activity.checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION)==PackageManager.PERMISSION_GRANTED ||
      activity.checkSelfPermission(Manifest.permission.ACCESS_COARSE_LOCATION)==PackageManager.PERMISSION_GRANTED;
  }
  private Location lastLocation(){
    if(!hasLocationPermission()||locations==null)return null;
    try{
      Location a=locations.getLastKnownLocation(LocationManager.GPS_PROVIDER);
      Location b=locations.getLastKnownLocation(LocationManager.NETWORK_PROVIDER);
      if(a==null)return b;if(b==null)return a;return a.getTime()>=b.getTime()?a:b;
    }catch(SecurityException|IllegalArgumentException e){return null;}
  }
  private void moveTo(Location loc){moveTo(loc,false);}
  private void moveTo(Location loc,boolean userInitiated) {
    if(loc==null||!Double.isFinite(loc.getLatitude())||!Double.isFinite(loc.getLongitude())||
      Math.abs(loc.getLatitude())>90||Math.abs(loc.getLongitude())>180)return;
    if(!hasFix){hasFix=true;followLocation=true;}
    if(userInitiated){followLocation=true;initialZoomSet=false;}
    if(!followLocation)return;
    long age=Math.max(0L,System.currentTimeMillis()-loc.getTime());
    boolean stale=loc.getTime()>0&&age>120000L;
    status.setText(stale?"GPS • ULTIMA POZIȚIE ("+(age/60000)+" min)":
      "GPS • POZIȚIE REALĂ"+(loc.hasAccuracy()?" ±"+Math.round(loc.getAccuracy())+"m":""));
    if(osm!=null){
      GeoPoint position=new GeoPoint(loc.getLatitude(),loc.getLongitude());
      if(gpsMarker==null){
        gpsMarker=new Marker(osm);
        gpsMarker.setAnchor(Marker.ANCHOR_CENTER,Marker.ANCHOR_BOTTOM);
        osm.getOverlays().add(gpsMarker);
      }
      gpsMarker.setPosition(position);
      gpsMarker.setTitle(stale?"Ultima poziție GPS":"Poziția mea • GPS");
      if(!initialZoomSet){osm.getController().setZoom(16.0);initialZoomSet=true;}
      osm.getController().animateTo(position);
      osm.invalidate();
    }
    if(googleMap!=null)googleMap.animateCamera(CameraUpdateFactory.newLatLngZoom(
      new LatLng(loc.getLatitude(),loc.getLongitude()),16f));
  }
  void onHostStart() {
    active=true;if(locations==null)locations=(LocationManager)activity.getSystemService(Activity.LOCATION_SERVICE);
    if(googleView!=null&&!mapStarted){googleView.onStart();mapStarted=true;}
    if(googleMap!=null&&hasLocationPermission())try{googleMap.setMyLocationEnabled(true);}catch(SecurityException ignored){}
    if(hasLocationPermission()&&locations!=null){
      Location l=lastLocation();if(l!=null)moveTo(l);
      try{locations.requestLocationUpdates(LocationManager.GPS_PROVIDER,2000,5f,this);
          locations.requestLocationUpdates(LocationManager.NETWORK_PROVIDER,5000,15f,this);}
      catch(SecurityException|IllegalArgumentException ignored){}
    }
  }
  void onHostResume(){if(googleView!=null&&!mapResumed){googleView.onResume();mapResumed=true;}if(osm!=null)osm.onResume();}
  void onHostPause(){
    if(googleView!=null&&mapResumed){googleView.onPause();mapResumed=false;}
    if(osm!=null)osm.onPause();
    if(locations!=null)try{locations.removeUpdates(this);}catch(SecurityException ignored){}
    active=false;
  }
  void onHostStop(){if(googleView!=null&&mapStarted){googleView.onStop();mapStarted=false;}}
  void onHostDestroy(){
    onHostPause();onHostStop();
    if(googleView!=null)googleView.onDestroy();
    if(osm!=null)osm.onDetach();
  }
  @Override public void onLocationChanged(Location l){if(active)moveTo(l);}
  @Override public void onStatusChanged(String provider,int status,Bundle extras){}
  @Override public void onProviderEnabled(String provider){}
  @Override public void onProviderDisabled(String provider){}
}
