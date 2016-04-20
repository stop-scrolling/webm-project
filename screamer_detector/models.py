from django.db import models

#TODO: Introduce content entity, move most fields into it. Video should contain references to this entity.
class Video(models.Model):
	url = models.CharField(max_length=2048, primary_key=True)
	size = models.PositiveIntegerField(default=0)
	md5 = models.CharField(max_length=32, default='')
	date_add = models.DateTimeField(auto_now_add=True)
	date_access = models.DateTimeField(auto_now=True)
	duration_msec = models.PositiveIntegerField(default=0)
	max_volume = models.DecimalField(max_digits=4, decimal_places=1, default=0)
	volume_range = models.DecimalField(max_digits=4, decimal_places=1, default=0)
	screamer_chance = models.PositiveSmallIntegerField(default=0)
	error = models.CharField(max_length=512)
	
	def __str__(self):
		return '%s: md5=%s size=%s max_volume=%f' % (self.url, self.md5, self.size, self.max_volume)