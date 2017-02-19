MediaToBBCode.py
==========

A Python script that combines the metadata output of [MediaInfo](http://mediaarea.net/en/MediaInfo) (either from an exported CSV file, or by directly parsing local video-clips), and combines it with the BBCode output of various image-hosts to automatically generate a BBCode-formatted presentation of a media-clips collection.

![Screenshot](screenshot.png)

Besides the aesthetics, there's value in having file metadata in your online posts/presentations. Image-hosts will not be online forever. This way, users can find and compare files longer into the future.

This script can save you quite a lot of time by automating the most tedious part of the output. It will also check to make sure that all your images are correctly paired with the file on each line.

## Features
- Parse CSV files generated by MediaInfo.
- Parse local media files (recursively or not) using the MediaInfo lib.
- Cleanup of media metadata.
- Detect image-set ZIP archives and provide information on their contents.
- Automated image matching with popular image-host BBCode output, as well as backup images.
- Output as BBCode for easy online use.
- Multiple layout options
- Automatically generate performer tags (as found in the file-names).

#### Requirements
- Python 3.4+ (not compatible with Python 2.7+)
- [MediaInfo](https://mediaarea.net/en/MediaInfo/Download)
    - 32/64bit dll/lib must match Python environment
- [pymediainfo](https://pypi.python.org/pypi/pymediainfo)

For Ubuntu this would be something like:
````
sudo apt install mediainfo
sudo apt install python3-pip
pip3 install pymediainfo
````

## Instructions
There are 2 basic workflows: using CSV or using direct media parsing.

### CSV workflow
1. Make sure you have all the required elements listed above.
1. Use [MediaInfo](http://mediaarea.net/en/MediaInfo) to export a CSV file with all the data of your video clips. Name it `my-clips.csv` and move it to the `./files` directory.
1. Use your favorite thumbnail maker application to create screenshots of all the videos. Make sure that the output images have the exact same file-name as the original videos (besides the extension obviously). But __don't__ include the original media extension in the output name. So `foo.mp4` should give `foo.jpg`, __not__ `foo.mp4.jpg`. 
1. Upload all the thumbnail images to one of the following image-hosts: *
    * [ImageBam.com](http://www.imagebam.com/)
    * [Postimage.io](https://postimage.io/)
    * [PiXhost.org](http://pixhost.org/)
    * [ImageTwist](http://imagetwist.com/)
    * [ImageVenue.com](http://imagevenue.com/)
    * [imgChili.net](http://imgchili.net/)
    * Adult content permitted: **
        * [PIXXXELS.org](http://pixxxels.org/)
        * [Jerking](https://jerking.empornium.ph/)
        * [Fapping](https://fapping.empornium.sx/)
1. Copy the Forum/BBCode output text as displayed on the host website after uploading, and paste it into a new txt file called `my-clips.txt`. ***
1. Put the txt file in the same(!) directory as `my-clips.csv` (usually `./files`)
1. Make sure the CSV file and the txt file have the same filename (e.g. `Michael-Jackson.csv` and `Michael-Jackson.txt`), otherwise the script won't be able to combine them.
1. Run `python3 mediatobbcode.py`. The default parameters should work for this example.
1. Copy the contents of the generated `my-clips_output.txt` into your presentation. You can usually find it in the `./files` directory.

\* _These image-hosts are supported because they all share one important similarity: the file-names for the uploaded images are predictable and the slugs are reproducable offline. Without that, we wouldn't be able to match our output to the correct online images._

\** _As requested by some anonymous users ;)._

\** _If you want to add an additional image-host as a backup in case the primary host goes down, simply add an extra txt containing the host's output in a file with the `_alt` suffix (`my-clips_alt.txt` in this example)_

#### CSV example
Files (relative paths in this example):
````
dir/
|-- mediatobbcode.py
|-- foo/
    |-- Michael Jackson videos.csv    (generated by MediaInfo)
    |-- Michael Jackson videos.txt    (BBCode output provided by image-host)
    |-- madonna-clips-collection.csv  (generated by MediaInfo)
    |-- madonna-clips-collection.txt  (BBCode output provided by image-host)
````
Run: `python3 mediatobbcode.py -d foo`

Output:
````
dir/
|-- foo/
    |-- Michael Jackson videos_output.txt    (fully formatted BBCode)
    |-- madonna-clips-collection_output.txt  (fully formatted BBCode)
````

### Media parsing workflow
5. Perform steps 3,4,5 from the CSV workflow
1. Rename the txt-file containing the image-host data to the directory name you want to parse. So if you want to parse `/home/me/Vids/Led Zeppelin`, name the file `Led Zeppelin.txt`. Place the file in the directory where you want your output files to be created (like `~/Desktop/output/`).
1. Run: `python3 mediatobbcode.py -d ~/Desktop/output/ -m "/home/me/Vids/Led Zeppelin"`
1. Copy the contents of the generated `Led Zeppelin_output.txt` into your presentation. You can usually find it in the `./files` directory.

#### Media parsing example
Files (absolute paths in this example):
````
/mnt/
|-- foo/
    |-- bar/
    |   |-- Michael Jackson - Live 95.mp4
    |   |-- Michael Jackson BTS.mov
    |-- Michael Jackson - Thriller.flv
    |-- Michael Jackson - Bad.mkv
    |-- Michael Jackson on Tour.wmv

~/Desktop/post one/foo.txt   (BBCode output with 3 or 5 entries, provided by image-host)
~/Desktop/post one/foo.txt   (BBCode output with 5 entries, provided by image-host)
````
Run: `python3 mediatobbcode.py -d "~/Desktop/post one" -m /mnt/foo`

Run: `python3 mediatobbcode.py -d "~/Desktop/post all" -m /mnt/foo -r` (recursive)

Output:
````
~/Desktop/post one/foo_output.txt   (fully formatted BBCode with 3 entries)
~/Desktop/post all/foo_output.txt   (fully formatted BBCode with 5 entries)
````

## Command-line options and arguments
##### File processing
* `-d <path>` or `--dir <path>` The working directory, where CSV files and/or image-lists should be located, and `_output.txt` files are written. All CSV files located here will be parsed, so make sure they are properly formatted by MediaInfo.
    * default: `./files`
* `-m <path>` or `--mediadir <path>` The directory to use when looking for video files to process. This switches the script from using CSV as input, to actually generating file information using MediaInfo as the script runs. Output files will be written to `-d`, or to `-m` if not specified.
    * default: `./videos`
    * requires: `MediaInfo`
* `-r` or `--recursive` Will enable recursive searching for media files. Meaning it will include all sub-directories of `-m`.
    * applies if: `-m`
* `-z` or `--zip` Will process all encountered ZIP archives as image-sets and provide information about their contents (number of images, image resolution, size, etc.)
    * applies if: `-m`
    * requires: [Pillow](https://python-pillow.org/)

##### Output formatting
* `-l` or `--list` Generates a simpler (and uglier) list instead of a table. Use this if the BBCode engine on your website doesn't support `[table]` tags.
* `-i` or `--individual` Generates a separate output file for each directory successfully traversed recursively (and named accordingly).
    * applies if: `-m` & `-r`
* `-f` or `--flat` Prevents the creation of separators (with the dir name) when switching directories in recursive mode.
    * applies if: `-m` & `-r` !& `-i`
* `-b` or `--bare` Stops the table heading from being automatically generated. Use this if the BBCode engine on your website doesn't support `[table]` tags or if you simply don't like it.
* `-u` or `--url` Embeds a simple link to the full-sized image in the output, rather than a thumbnail (which links to the same image). Use this if the BBCode engine on your website doesn't support `[spoiler]` tags.
* `-t` or `--tinylink` Instead of the whole file-name being a link to the full-sized image (or a `[spoiler]` tag), a smaller link to the same image will be inserted in the row instead.
* `-s` or `--suppress` Prevents warning messages from appearing in the output if no suitable image or image-link was found.
* `-a` or `--all` Will output all 7 different layout options below each other, easy for testing and picking your favorite. Note that this will include layouts with `[table]` and `[spoiler]` tags, so be careful if these aren't supported.
* `-x` or `--xdebug` For debugging image-host output slugs. Only for developers.

### Support

If you're having problems with the script, pay close attention to the messages in the console. There will be very little (if any) support from me.

### Disclaimer

I've only tested this with Python 3.4, 3.5 and 3.6, both on Windows 10 and Ubuntu. I've tried various media files, but there are quite a lot of video/audio codecs out there in the world, and whether MediaInfo can process them correctly is not a sure thing. A few manual fixes to correct the metadata have been added, but there's bound to be some codecs/formats that slipped by. In short: your mileage may vary. Use at your own risk.

### License
[GNU General Public License v3](http://opensource.org/licenses/GPL-3.0)

© 2017 - PayBas
