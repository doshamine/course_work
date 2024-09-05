import configparser
import json
import time
from tqdm import tqdm
import requests


tqdm_fmt = {
	'colour': '#9932CC',
	'bar_format': '{l_bar}{bar}| {n_fmt}/{total_fmt}'
}


def response_processing(response):
	"""Анализирует ответ сервера. В случае ошибки выводит сообщение в консоль.

	Параметры:
	response -- объект класса requests.models.Response, полученный в результате выполнения http-запроса.
	"""
	code = response.status_code
	if 400 <= code < 500:
		print(f'Client error {code}')
		exit()

	elif 500 <= code < 600:
		print(f'Server error {code}')
		exit()

	response_json = response.json()
	if response_json.get('error') is not None:
		print(f"Error. {response_json['error']['error_msg']}")
		exit()


class VKClient:
	"""Класс для получения информации о фотографиях из альбома ВК."""
	BASE_URL = 'https://api.vk.com/method'

	def __init__(self, vk_token: str, user_id: str, version='5.199'):
		self.__params = {
			'access_token': vk_token, 
			'owner_id': user_id, 'extended': '1', 
			'v': version
		}

	def get_photos_info(self, album_id) -> list:
		"""Получает информацию о фотографиях из конкретного альбома ВК.

		   Параметры:
		   album_id -- id альбома с фотографиями.

		   Возвращаемое значение:
		   Список словарей, содержащих информацию о фотографиях.
		   likes -- количество лайков на фото.
		   url -- ссылка на фотографию.
		   date -- дата загрузки (число секунд с начала "эпохи").
		   height, width -- размеры фото.
		"""
		url = f'{VKClient.BASE_URL}/photos.get'
		params = {'album_id': album_id}
		response = requests.get(url, params={**self.__params, **params})
		response_processing(response)
		response_json = response.json()
		items = response_json['response']['items']

		output_info = []
		for item in tqdm(items, **tqdm_fmt):
			output_info.append({
				'likes': item['likes']['count'], 'url': item['orig_photo']['url'], 
				'date': item['date'], 'height': item['orig_photo']['height'],
				'width': item['orig_photo']['width']
			})

		return output_info


class DiskClient:
	"""Класс для загрузки файлов в папку на Яндекс Диске."""
	BASE_URL = 'https://cloud-api.yandex.net/v1/disk/resources'

	def __init__(self, ya_token: str):
		self.__headers = {'Authorization': ya_token}

	def __create_dir(self, dirname: str) -> dict:
		"""Создаёт новую папку на диске.

		   Параметры:
		   dirname -- полный путь к новой папке.

		   Возвращаемое значение:
		   Словарь - ответ сервера в json-формате.
		"""
		params = {'path': dirname}
		response = requests.put(DiskClient.BASE_URL, params=params, headers=self.__headers)
		response_processing(response)
		response_json = response.json()

		return response_json

	def upload_files(self, files_info: list, dirname='reserve_copy') -> dict:
		"""Загружает файлы в папку на диске.

		   Параметры:
		   files_info - список словарей с информацией о файлах.
		   dirname -- полный путь к новой папке (по умолчанию - ./reserve_copy).

		   Возвращаемое значение:
		   Словарь с информацией о созданной папке и загруженных туда файлах.
		   href -- ссылка на созданную папку.
		   name -- имя созданной папки.
		   date -- дата создания папки (число секунд с начала "эпохи").
		   count -- количество загруженных файлов.
		   items -- список словарей с информацией о загруженных файлах:
		      name -- имя файла.
		      href -- ссылка на загруженную фотографию.
		      height, width -- размеры фотографии.
		"""
		names = [info['likes'] for info in files_info]
		duplicate_names = {name if names.count(name) > 1 else None for name in names}
		
		create_dir_json = self.__create_dir(dirname)
		url = f'{DiskClient.BASE_URL}/upload'
		output_json = {
			'href': create_dir_json['href'], 
			'name': dirname, 'date': time.time(),
			'count': len(files_info),
			'items': []
		}

		for info in tqdm(files_info, **tqdm_fmt):
			base_name = f"{info['likes']}"
			filename = base_name + f"-{time.strftime('%d_%m_%Y', time.localtime(info['date']))}" if info['likes'] in duplicate_names else base_name
			params = {'path': f'{dirname}/{filename}', 'url': info['url']}
			response = requests.post(url, headers=self.__headers, params=params)
			response_processing(response)
			response_json = response.json()
			output_json['items'].append({
				'name': filename, 'href': response_json['href'],
				'height': info['height'], 'width': info['width'] 
			})

		return output_json



if __name__ == '__main__':
	config = configparser.ConfigParser()
	config.read('settings.ini')
	vk_token = config['VK']['vk_token']
	user_id = input('Enter vk user id: ')
	album_id = input("Enter album id ('profile' by default): ")
	if not album_id:
		album_id = 'profile'

	vk_client = VKClient(vk_token, user_id, album_id)
	photos_info = vk_client.get_photos_info()
	print()

	disk_token = input('Enter disk access token: ')
	dirname = input('Enter directory name (default: reserve_copy): ')

	yadisk_client = DiskClient(disk_token)
	response_json = yadisk_client.upload_files(photos_info, dirname)
	
	with open('output.json', 'w') as file:
		json.dump(response_json, file, ensure_ascii=False, indent=2)

	print('Done!')

