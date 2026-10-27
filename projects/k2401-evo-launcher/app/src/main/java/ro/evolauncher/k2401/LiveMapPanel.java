package ro.evolauncher.k2401;

import android.Manifest;
import android.app.Activity;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.location.Location;
import android.location.LocationListener;
import android.location.LocationManager;
import android.os.Bundle;
import android.view.Gravity;
import android.view.View;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.TextView;
import com.google.android.gms.common.ConnectionResult;
import com.google.android.gms.common.GoogleApiAvailability;
import com.google.android.gms.maps.CameraUpdateFactory;
import com.google.android.gms.maps.GoogleMap;
import com.google.android.gms.maps.MapView;
import com.google.android.gms.maps.model.LatLng;
import com.google.android.gms.maps.model.MapStyleOptions;
import java.util.Locale;

/** Actual interactive basemap, never a simulated route or simulated GPS.
 * With a restricted Maps SDK key and Play Services: embedded Google Map.
 * Without credentials: a clearly labeled OpenStreetMap basemap (internet required).
 * Route guidance is delegated to the installed Google Maps application.
 */
final class LiveMapPanel extends FrameLayout implements LocationListener {
  // Real Google Maps SDK vector styling, never a simulated basemap.
  private static final String DARK_MAP_STYLE="[{\"elementType\":\"geometry\",\"stylers\":[{\"color\":\"#17202b\"}]},{\"elementType\":\"labels.text.fill\",\"stylers\":[{\"color\":\"#9ba9b8\"}]},{\"elementType\":\"labels.text.stroke\",\"stylers\":[{\"color\":\"#101822\"}]},{\"featureType\":\"road\",\"elementType\":\"geometry\",\"stylers\":[{\"color\":\"#293747\"}]},{\"featureType\":\"road.highway\",\"elementType\":\"geometry\",\"stylers\":[{\"color\":\"#495768\"}]},{\"featureType\":\"water\",\"elementType\":\"geometry\",\"stylers\":[{\"color\":\"#0b2333\"}]},{\"featureType\":\"poi\",\"stylers\":[{\"visibility\":\"off\"}]}]";
  private final Activity activity;
  private MapView googleView;
  private GoogleMap googleMap;
  private WebView openMap;
  private LocationManager locations;
  private boolean active;
  private boolean hasFix;
  private boolean mapStarted;
  private boolean mapResumed;
  private final boolean usingGoogle;
  private final TextView label;

  LiveMapPanel(Activity activity){
    super(activity);
    this.activity=activity;
    setBackgroundColor(0xff182332);
    setClipToPadding(true);
    boolean canGoogle=BuildConfig.GOOGLE_MAPS_CONFIGURED &&
        GoogleApiAvailability.getInstance().isGooglePlayServicesAvailable(activity)==ConnectionResult.SUCCESS;
    usingGoogle=canGoogle;
    if(canGoogle){
      googleView=new MapView(activity);
      addView(googleView,new FrameLayout.LayoutParams(-1,-1));
      googleView.onCreate(null);
      googleView.getMapAsync(map->{
        googleMap=map;
        try{map.setMapStyle(new MapStyleOptions(DARK_MAP_STYLE));}catch(RuntimeException ignored){}
        map.getUiSettings().setZoomControlsEnabled(true);
        map.getUiSettings().setCompassEnabled(true);
        if(hasLocationPermission()) {
          try{map.setMyLocationEnabled(true);}catch(SecurityException ignored){}
        }
        Location fix=lastLocation();
        if(fix!=null)moveTo(fix);
      });
    }else{
      openMap=new WebView(activity);
      openMap.setBackgroundColor(0xff182332);
      openMap.getSettings().setJavaScriptEnabled(true);
      openMap.getSettings().setDomStorageEnabled(true);
      openMap.getSettings().setAllowFileAccess(false);
      openMap.getSettings().setAllowContentAccess(false);
      openMap.getSettings().setCacheMode(WebSettings.LOAD_DEFAULT);
      openMap.getSettings().setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
      openMap.getSettings().setUserAgentString(openMap.getSettings().getUserAgentString()+" EVO-Launcher-K2401/0.3");
      addView(openMap,new FrameLayout.LayoutParams(-1,-1));
      // OpenStreetMap tiles are third-party online content with visible attribution.
      // No scraping, no offline bulk prefetch and no fabricated turn-by-turn route.
      String html="<!doctype html><html><head><meta name='viewport' content='width=device-width,initial-scale=1,maximum-scale=1'>" +
        "<link rel='stylesheet' href='https://unpkg.com/leaflet@1.9.4/dist/leaflet.css'/>" +
        "<style>html,body,#m{height:100%;width:100%;margin:0;background:#172331}.leaflet-tile-pane img{filter:brightness(.72) invert(1) hue-rotate(180deg) saturate(.55)}</style></head><body><div id='m'></div>" +
        "<script src='https://unpkg.com/leaflet@1.9.4/dist/leaflet.js'></script><script>" +
        "var evoMap=L.map('m',{zoomControl:true}).setView([0,0],2);" +
        "L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'&copy; OpenStreetMap contributors'}).addTo(evoMap);" +
        "var pin=null;function setEvoLocation(a,b){evoMap.setView([a,b],16);if(pin){pin.setLatLng([a,b]);}else{pin=L.circleMarker([a,b],{radius:7,color:'#ef2840',fillOpacity:0.9}).addTo(evoMap);}}" +
        "</script></body></html>";
      openMap.loadDataWithBaseURL("https://www.openstreetmap.org/",html,"text/html","UTF-8",null);
    }
    label=new TextView(activity);
    label.setText(canGoogle?"GOOGLE MAPS • LIVE":"HARTĂ LIVE • OpenStreetMap");
    label.setTextColor(Color.WHITE);
    label.setTextSize(12);
    label.setBackgroundColor(0xcc101720);
    label.setPadding(9,6,9,6);
    FrameLayout.LayoutParams tag=new FrameLayout.LayoutParams(-2,-2,Gravity.TOP|Gravity.RIGHT);
    tag.setMargins(8,9,8,0);addView(label,tag);

    Button google=new Button(activity);
    google.setText("RUTĂ GOOGLE MAPS");
    google.setTextSize(11);
    google.setTextColor(Color.WHITE);
    google.setBackgroundTintList(android.content.res.ColorStateList.valueOf(0xff9d2035));
    FrameLayout.LayoutParams btn=new FrameLayout.LayoutParams(-2,53,Gravity.BOTTOM|Gravity.CENTER_HORIZONTAL);
    btn.bottomMargin=14;addView(google,btn);
    google.setOnClickListener(v->{if(activity instanceof MainActivity)((MainActivity)activity).maps();});
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
      if(a==null)return b;if(b==null)return a;
      return a.getTime()>=b.getTime()?a:b;
    }catch(IllegalArgumentException|SecurityException e){return null;}
  }
  private void moveTo(Location loc){
    if(loc==null||loc.getLatitude()<-90||loc.getLatitude()>90||
       loc.getLongitude()<-180||loc.getLongitude()>180)return;
    if(!hasFix){hasFix=true;}
    double lat=loc.getLatitude(),lon=loc.getLongitude();
    if(googleMap!=null)googleMap.animateCamera(CameraUpdateFactory.newLatLngZoom(new LatLng(lat,lon),16));
    if(openMap!=null)openMap.evaluateJavascript(String.format(Locale.US,"if(window.setEvoLocation){setEvoLocation(%.7f,%.7f)}",lat,lon),null);
  }
  void onHostStart(){
    active=true;
    if(locations==null)locations=(LocationManager)activity.getSystemService(Activity.LOCATION_SERVICE);
    if(googleView!=null&&!mapStarted){googleView.onStart();mapStarted=true;}
    if(googleMap!=null&&hasLocationPermission()){try{googleMap.setMyLocationEnabled(true);}catch(SecurityException ignored){}}
    if(hasLocationPermission()&&locations!=null){
      Location prev=lastLocation();if(prev!=null)moveTo(prev);
      try{
        locations.requestLocationUpdates(LocationManager.GPS_PROVIDER,2000L,5f,this);
        locations.requestLocationUpdates(LocationManager.NETWORK_PROVIDER,5000L,25f,this);
      }catch(SecurityException|IllegalArgumentException ignored){}
    }
  }
  void onHostResume(){
    if(googleView!=null&&!mapResumed){googleView.onResume();mapResumed=true;}
  }
  void onHostPause(){
    if(googleView!=null&&mapResumed){googleView.onPause();mapResumed=false;}
    if(locations!=null){try{locations.removeUpdates(this);}catch(SecurityException ignored){}}
    active=false;
  }
  void onHostStop(){if(googleView!=null&&mapStarted){googleView.onStop();mapStarted=false;}}
  void onHostDestroy(){
    onHostPause();onHostStop();
    if(googleView!=null)googleView.onDestroy();
    if(openMap!=null){openMap.stopLoading();openMap.loadUrl("about:blank");openMap.destroy();openMap=null;}
  }
  @Override public void onLocationChanged(Location loc){if(active)moveTo(loc);}
  @Override public void onStatusChanged(String provider,int status,Bundle extras){}
  @Override public void onProviderEnabled(String provider){}
  @Override public void onProviderDisabled(String provider){}
}
