document.addEventListener("DOMContentLoaded", () => {
  const videos = Array.from(
    document.querySelectorAll(".video-background .background-video")
  );
  if (videos.length === 0) {
    return;
  }

  const playVideo = (video) => {
    const playback = video.play();
    if (playback && typeof playback.catch === "function") {
      playback
        .then(() => video.classList.add("is-active"))
        .catch((error) => {
          console.error(`No se pudo reproducir el video ${video.currentSrc}.`, error);
        });
    } else {
      video.classList.add("is-active");
    }
  };

  videos.forEach((video, index) => {
    video.loop = false;
    video.addEventListener("ended", () => {
      video.classList.remove("is-active");
      const nextVideo = videos[(index + 1) % videos.length];
      const startNext = () => {
        nextVideo.currentTime = 0;
        playVideo(nextVideo);
      };

      if (nextVideo.readyState > 0) {
        startNext();
      } else {
        nextVideo.addEventListener("loadedmetadata", startNext, { once: true });
      }
    });
  });

  playVideo(videos[0]);
});
