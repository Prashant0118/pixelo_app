from django.urls import path 
from . import views
from .views import ping_view

profile_menu_view = getattr(views, "profile_menu", views.edit_profile)

urlpatterns = [
    path('ping/', ping_view),
    path('manifest.webmanifest', views.pwa_manifest, name='pwa_manifest'),
    path('service-worker.js', views.pwa_service_worker, name='pwa_service_worker'),
    path('offline/', views.offline, name='offline'),
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('forgot-password/verify/', views.verify_password_reset_otp, name='verify_password_reset_otp'),
    path('forgot-password/reset/', views.reset_password, name='reset_password'),
    path('logout/', views.user_logout, name='logout'),
    path("notifications/", views.notifications, name="notifications"),
    path("chat/", views.chat_inbox, name='chat_inbox'),
    path("chat/<str:username>/", views.chat, name='chat'),
    path("chat-lock/<str:username>/", views.lock_chat, name="lock_chat"),
    path("chat-api/<str:username>/messages/", views.chat_messages_api, name="chat_messages_api"),
    path("chat-api/<str:username>/send/", views.chat_send_api, name="chat_send_api"),
    path("chat-api/<str:username>/delete/<int:message_id>/", views.chat_delete_api, name="chat_delete_api"),
    path('search/', views.search, name="search"),
    path('search-suggestions/', views.search_suggestions, name="search_suggestions"),
    path('upload/', views.upload, name="upload"),
    path('upload/chunk/', views.upload_chunk, name="upload_chunk"),
    path('upload/chunk/complete/', views.upload_chunk_complete, name="upload_chunk_complete"),
    path('upload/cloudinary-signature/', views.cloudinary_signature, name="cloudinary_signature"),
    path('upload/cloudinary-complete/', views.cloudinary_complete_upload, name="cloudinary_complete_upload"),
    path('story/upload/', views.upload_story, name="upload_story"),
    path('story/music-search/', views.story_music_search_api, name="story_music_search_api"),
    path('story/archive/', views.story_archive, name="story_archive"),
    path('story/archive/<int:story_id>/toggle-highlight/', views.toggle_story_highlight, name="toggle_story_highlight"),
    path('story/<int:story_id>/', views.view_story, name="view_story"),
    path('reels/', views.reels, name="reels"),
    path('reel-watch/<int:post_id>/', views.reel_watch_ping, name='reel_watch_ping'),
    path('post-watch/<int:post_id>/', views.post_watch_ping, name='post_watch_ping'),
    path('profile/<str:username>/', views.profile, name="profile"),
    path('profile-menu/', profile_menu_view, name='profile_menu'),

    path('edit-profile/', views.edit_profile, name='edit_profile'),
    path('payment-settings/', views.payment_settings, name='payment_settings'),
    path('edit-bio/', views.edit_bio, name='edit_bio'),
    path('unfollow/<str:username>/', views.unfollow, name='unfollow'),
    path("follow/<str:username>/", views.send_follow_request, name="follow"),
    path("followers/<str:username>/", views.followers_list, name="followers_list"),
    path("following/<str:username>/", views.following_list, name="following_list"),
    path('like-ajax/<int:post_id>/', views.like_ajax, name='like_ajax'),
    path('comment-ajax/<int:post_id>/', views.comment_ajax, name='comment_ajax'),
    path('save-post/<int:post_id>/', views.save_post, name='save_post'),
    path('share-post/<int:post_id>/', views.share_post_to_follower, name='share_post_to_follower'),
    path('post-share-preview/<int:post_id>/', views.post_share_preview, name='post_share_preview'),
    path('saved-posts/', views.saved_posts, name='saved_posts'),
    path('liked-reels/', views.liked_reels, name='liked_reels'),
    path('delete-comment/<int:comment_id>/', views.delete_comment, name='delete_comment'),
    path('delete-post/<int:post_id>/', views.delete_post, name='delete_post'),





]
