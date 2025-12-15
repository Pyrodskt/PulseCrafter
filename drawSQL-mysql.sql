CREATE TABLE `Musics`(
    `id_music` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `music_name` VARCHAR(255) NOT NULL,
    `file_path` VARCHAR(255) NOT NULL,
    `bpm` BIGINT NOT NULL,
    `sub_bass_db` FLOAT(53) NOT NULL,
    `mid_bass_db` FLOAT(53) NOT NULL,
    `punchiness` FLOAT(53) NOT NULL,
    `id_tonality` BIGINT NOT NULL,
    `id_artist` BIGINT NOT NULL,
    `id_music_gender` BIGINT NOT NULL,
    `id_bass_type` BIGINT NOT NULL
);
CREATE TABLE `Artists`(
    `id_artist` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `artist_name` VARCHAR(255) NOT NULL
);
CREATE TABLE `Tonalitys`(
    `id_tonality` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `tonality_name` VARCHAR(255) NOT NULL,
    `tonality_note` VARCHAR(255) NOT NULL,
    `tonality_key` VARCHAR(255) NOT NULL
);
CREATE TABLE `music_gender`(
    `id_music_gender` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `music_gender_name` BIGINT NOT NULL
);
CREATE TABLE `music_groups`(
    `id_music_groups` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `music_group_name` VARCHAR(255) NOT NULL
);
CREATE TABLE `playlists`(
    `id_playlist` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `playlist_name` VARCHAR(255) NOT NULL
);
CREATE TABLE `music_group_has_music`(
    `id_music_group_has_music` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `id_music` BIGINT NOT NULL,
    `id_music_group` BIGINT NOT NULL
);
CREATE TABLE `playlist_has_music`(
    `id_playlist_has_music` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `id_playlist` BIGINT NOT NULL,
    `id_music` BIGINT NOT NULL
);
CREATE TABLE `bass_type`(
    `id_bass_type` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
    `bass_type_name` VARCHAR(255) NOT NULL
);
ALTER TABLE
    `Musics` ADD CONSTRAINT `musics_id_music_gender_foreign` FOREIGN KEY(`id_music_gender`) REFERENCES `music_gender`(`id_music_gender`);
ALTER TABLE
    `Musics` ADD CONSTRAINT `musics_id_bass_type_foreign` FOREIGN KEY(`id_bass_type`) REFERENCES `bass_type`(`id_bass_type`);
ALTER TABLE
    `playlist_has_music` ADD CONSTRAINT `playlist_has_music_id_music_foreign` FOREIGN KEY(`id_music`) REFERENCES `Musics`(`id_music`);
ALTER TABLE
    `music_group_has_music` ADD CONSTRAINT `music_group_has_music_id_music_group_foreign` FOREIGN KEY(`id_music_group`) REFERENCES `music_groups`(`id_music_groups`);
ALTER TABLE
    `Musics` ADD CONSTRAINT `musics_id_tonality_foreign` FOREIGN KEY(`id_tonality`) REFERENCES `Tonalitys`(`id_tonality`);
ALTER TABLE
    `Musics` ADD CONSTRAINT `musics_id_artist_foreign` FOREIGN KEY(`id_artist`) REFERENCES `Artists`(`id_artist`);
ALTER TABLE
    `music_group_has_music` ADD CONSTRAINT `music_group_has_music_id_music_foreign` FOREIGN KEY(`id_music`) REFERENCES `Musics`(`id_music`);
ALTER TABLE
    `playlist_has_music` ADD CONSTRAINT `playlist_has_music_id_playlist_foreign` FOREIGN KEY(`id_playlist`) REFERENCES `playlists`(`id_playlist`);