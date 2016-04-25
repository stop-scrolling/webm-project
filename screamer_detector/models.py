from django.db import models

class Content(models.Model):
	md5 = models.CharField(max_length=32, default='', primary_key=True) #TODO: Primary key should be md5+size.
	size = models.PositiveIntegerField(default=0)
	date_add = models.DateTimeField(auto_now_add=True)
	date_access = models.DateTimeField(auto_now=True)
	duration_msec = models.PositiveIntegerField(default=0)
	max_volume = models.DecimalField(max_digits=4, decimal_places=1, default=0)
	volume_range = models.DecimalField(max_digits=4, decimal_places=1, default=0)
	screamer_chance = models.PositiveSmallIntegerField(default=0)
	
	def __str__(self):
		return "md5=%s size=%s max_volume=%f" % (self.md5, self.size, self.max_volume)

class URL(models.Model):
	url = models.CharField(max_length=2048, primary_key=True)
	content = models.ForeignKey(Content, on_delete=models.SET_NULL, null=True)
	date_add = models.DateTimeField(auto_now_add=True)
	date_access = models.DateTimeField(auto_now=True)
	error = models.CharField(max_length=512)

	def __str__(self):
		return "%s error: '%s' content: '%s'" % (self.url, self.error, str(self.content))

# class ProcessingQueue(models.Model):
# 	url = models.CharField(max_length=2048, primary_key=True)
# 	processing_id = models.PositiveIntegerField(default=0)
# 	date_add = models.DateTimeField(auto_now_add=True)

# 	def __str__(self):
# 		return "%s - %d", (self.url, self.processing_id)