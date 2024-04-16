import requests
import subprocess
import itertools
import glob
import os


class MissionHandler:
    def __init__(self, tmp_dir, dst_dir, steamcmd_path):
        """
        MissionHandler will enumerate all files in a Steam Workshop collection, download them, and rename them to their
            proper names (since Steam downloads them with a temp name)
        Useful to download Arma 3 missions since a straight steamcmd approach would result in a mission name of e.g.
            "816750855435742111_legacy.bin", which is 100% unusable by Arma
        :param tmp_dir:
            Directory to stage downloaded files in
            Note that subdirectories are automatically created within this directory by Steam
        :param dst_dir:
            Directory to place named files into
            Note that if this is for Arma, it should include "mpmissions" at the end
        :param steamcmd_path:
            Path to steamcmd - either Windows or Linux works, but it's up to you to pass the correct path format
        """
        self.collection_url = 'https://api.steampowered.com/ISteamRemoteStorage/GetCollectionDetails/v1/'
        self.file_url = 'https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/'
        self.tmp_dir = tmp_dir
        self.dst_dir = dst_dir
        self.steamcmd_path = steamcmd_path

    def _nuke_steam_cache_(self, app_id):
        """
        Delete the Steam workshop cache or files don't get re-downloaded even if we explicitly request them to be
        :param app_id:
            ID of the app we're nuking the cache for
        :return:
            N/A
        """
        try:
            os.remove(
                os.path.join(
                    self.tmp_dir,
                    'steamapps',
                    'workshop',
                    'appworkshop_{}.acf'.format(app_id),
                )
            )
        except FileNotFoundError:
            print("[WARN]: Couldn't find cache; did it exist?")

    def _get_collection_details_(self, collection_id):
        """
        Get a list of items in the collection
        :param collection_id:
            ID of the collection to enumerate items within
        :return:
            LIST of file IDs (which are themselves INTs)
        """
        reply = requests.post(
            self.collection_url,
            data={
                'collectioncount': 1,
                'publishedfileids[0]': collection_id,
            }
        )
        reply.raise_for_status()
        return [int(x['publishedfileid']) for x in reply.json()['response']['collectiondetails'][0]['children']]

    def _get_file_details_(self, file_ids):
        """
        Given the ID of a file, lookup metadata such as the desired file name
        :param file_ids:
            LIST of file IDs to get file names for
        :return:
            DICT of file id: file name
        """
        data = {
            'itemcount': len(file_ids),
        }

        for x, file_id in enumerate(file_ids):
            data['publishedfileids[{}]'.format(x)] = file_id

        reply = requests.post(
            self.file_url,
            data=data,
        )
        reply.raise_for_status()
        mapping = {}
        for details in reply.json()['response']['publishedfiledetails']:
            if details['filename']:
                mapping[details['publishedfileid']] = details['filename']
            elif details['title']:
                print("[INFO]: {} has no filename associated with it, falling back to title".format(details['publishedfileid']))
                mapping[details['publishedfileid']] = details['title']
            else:
                print("[WARN]: {} has no filename associated with it".format(details['publishedfileid']))
        return mapping

    def _download_files_(self, user, app_id, file_ids):
        """
            Given a list of file IDs, download them to the staging directory
        :param user:
            STRING - user to log in to steamcmd with
            Note that a password is not required as steamcmd caches credentials
        :param app_id:
            ID of the app these files are associated with
            Required because steam puts them into a subfolder under the app ID
        :param file_ids:
            List of file IDs to download
        :return:
            N/A
            Downloaded files will be placed in the tmp dir
        """
        # reformat file IDs to include the steamcmd command
        file_ids = ['+workshop_download_item {} {}'.format(app_id, x) for x in file_ids]
        # reformat so we can pass this to a subprocess call
        file_ids.insert(0, self.steamcmd_path)
        file_ids.insert(1, '+login {}'.format(user))
        file_ids.insert(2, '+force_install_dir {}'.format(self.tmp_dir))
        file_ids.append('validate')
        file_ids.append('+quit')
        # old code. I don't remember why this is needed, but I'm sure it totally is
        args = tuple(itertools.chain.from_iterable([x] for x in file_ids))
        subprocess.check_call(args)

    def _move_file_(self, app_id, file_mapping, mission=False):
        """
        Given a dict of file IDs: file names, move files from the tmp dir to the dst dir (renaming them in the process)
        :param app_id:
            ID of the app these files belong to
        :param file_mapping:
            DICT of file ID: file name
        :param mission:
            Unused at the moment. Mods in Arma follow a convention with "@" placed at the front, but Steam does not
                automatically do this
        :return:
            N/A
            Specified files will be moved from tmp_dir to dst_dir
        """
        for file_id, file_name in file_mapping.items():
            src = os.path.join(
                self.tmp_dir,
                'steamapps',
                'workshop',
                'content',
                str(app_id),
            )
            try:
                # find matching files in the workshop download path since we don't know the downloaded name, only the
                # desired name
                src = os.path.join(
                    src,
                    glob.glob(
                        os.path.join(
                            src,
                            str(file_id),
                            '*',
                        ),
                    )[0],
                )
            except Exception as e:
                print("[ERROR]: Looks like we failed to download {} - {}".format(file_name, e))
                continue
            dst = os.path.join(
                self.dst_dir,
                file_name,
            )
            try:
                if os.path.isfile(dst):
                    os.remove(dst)
                os.rename(src, dst)
            except Exception as e:
                print("[ERROR]: {}".format(e))

    def download_collection(self, app_id, collection_id, user):
        """
        Given a collection of workshop items, download them and move them to a destination directory
        :param app_id:
            ID of the app the files are associated with
            Needed because Steam places each workshop item under a directory with the app ID
        :param collection_id:
            ID of the collection to download
            You can grab this from the URL if you navigate to it in a browser
        :param user:
            User to log into steamcmd with
            No password is needed because steamcmd caches credentials. Note that if you haven't logged in to the account
                recently, you may be prompted (by steamcmd) to enter credentials
        :return:
            N/A
        """
        self._nuke_steam_cache_(app_id)
        files_to_download = self._get_collection_details_(collection_id)
        file_mapping = self._get_file_details_(files_to_download)
        self._download_files_(user, app_id, file_mapping.keys())
        self._move_file_(app_id, file_mapping)


if __name__ == '__main__':
    """
    Example usage
    """
    m = MissionHandler(
        tmp_dir='C:\\steamcmd\\my_tmp',
        dst_dir='C:\\steamcmd\\my_dst',
        steamcmd_path='C:\\steamcmd\\steamcmd.exe',
    )
    m.download_collection(
        app_id=107410,
        collection_id=1730420775,
        user='your_username',
    )
