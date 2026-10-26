package ro.evolauncher.k2401;
import android.service.notification.NotificationListenerService;
public final class MediaAccessService extends NotificationListenerService{
 @Override public void onListenerConnected(){super.onListenerConnected();MainActivity.changed();}
 @Override public void onNotificationPosted(android.service.notification.StatusBarNotification s){MainActivity.changed();}
 @Override public void onNotificationRemoved(android.service.notification.StatusBarNotification s){MainActivity.changed();}
}