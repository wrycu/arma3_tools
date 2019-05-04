import requests
import subprocess
import itertools
import glob
import os


class MissionHandler:
    def __init__(self, temp_dir, dst_dir, steamcmd_path):
        """
        make requests to API
        parse api responses
        download collection data
        parse out the IDs
        get mission details from other endpoint
        download all the missions using steamcmd
        rename and move missions to target dir with name fetched earlier
        """
        self.collection_url = 'https://api.steampowered.com/ISteamRemoteStorage/GetCollectionDetails/v1/'
        self.file_url = 'https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/'
        self.tmp_dir = temp_dir
        self.dst_dir = dst_dir
        self.steamcmd_path = steamcmd_path

    def _nuke_steam_cache_(self, app_id):
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
            else:
                print("[WARN]: {} has no filename associated with it".format(details['publishedfileid']))
        return mapping

    def _download_file_(self, user, app_id, file_ids):
        if not isinstance(file_ids, list):
            file_ids = [file_ids]
        file_ids = ['+workshop_download_item {} {}'.format(app_id, x) for x in file_ids]
        file_ids.insert(0, self.steamcmd_path)
        file_ids.insert(1, '+login {}'.format(user))
        file_ids.insert(2, '+force_install_dir {}'.format(self.tmp_dir))
        file_ids.append('validate')
        file_ids.append('+quit')
        # old code. I don't remember why this is needed, but I'm sure it totally is
        args = tuple(itertools.chain.from_iterable([x] for x in file_ids))
        subprocess.check_call(args)

    def _move_file_(self, app_id, file_mapping, mission=False):
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
        self._nuke_steam_cache_(app_id)
        files_to_download = self._get_collection_details_(collection_id)
        file_mapping = self._get_file_details_(files_to_download)
        self._download_file_(user, app_id, file_mapping.keys())
        self._move_file_(app_id, file_mapping)


if __name__ == '__main__':
    m = MissionHandler('C:\\steamcmd\\my_tmp', 'C:\\steamcmd\\my_dst', 'C:\\steamcmd\\steamcmd.exe')
    m.download_collection(107410, 1730420775, 'username')
