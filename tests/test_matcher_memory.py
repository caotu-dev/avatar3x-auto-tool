import unittest
from unittest.mock import patch
import cv2
import numpy as np
from vision.matcher import find_template,ROI

class MatcherMemoryTests(unittest.TestCase):
 def test_tiny_room_anchor_retries_allocation_failure_in_bounded_strips(self):
  rng=np.random.default_rng(77)
  image=rng.integers(0,256,(900,1600),dtype=np.uint8)
  template=image[380:398,901:961].copy()
  original=cv2.matchTemplate;heights=[]
  def constrained(region,*args):
   heights.append(region.shape[0])
   if region.shape[0]>100:raise MemoryError('simulated native allocation pressure')
   return original(region,*args)
  with patch('vision.matcher.cv2.matchTemplate',side_effect=constrained):
   found=find_template(image,template,.98,contrast_invariant=True)
  self.assertEqual((found.x,found.y),(901,380))
  self.assertEqual(heights[0],900)
  self.assertLessEqual(max(heights[1:]),81)

 def test_non_memory_opencv_failure_is_not_hidden(self):
  error=cv2.error('invalid input');error.code=-215
  with patch('vision.matcher.cv2.matchTemplate',side_effect=error) as match:
   with self.assertRaises(cv2.error):find_template(np.eye(80,dtype=np.uint8),np.eye(18,dtype=np.uint8))
  self.assertEqual(match.call_count,1)

 def test_opencv_allocation_error_uses_small_strip_fallback(self):
  image=np.random.default_rng(1).integers(0,256,(180,230),dtype=np.uint8)
  template=image[100:118,85:145].copy();original=cv2.matchTemplate
  error=cv2.error('Insufficient memory');error.code=-4
  def constrained(region,*args):
   if region.shape[0]>100:raise error
   return original(region,*args)
  with patch('vision.matcher.cv2.matchTemplate',side_effect=constrained):
   found=find_template(image,template,contrast_invariant=True)
  self.assertEqual((found.x,found.y),(85,100))

 def test_strip_matches_full_response_across_boundary_and_roi(self):
  rng=np.random.default_rng(7)
  for channels in (None,3):
   shape=(400,500) if channels is None else (400,500,channels)
   image=rng.integers(0,256,shape,dtype=np.uint8)
   template=image[147:170,201:232].copy()
   for contrast in (False,True):
    roi=ROI(.1,.1,.8,.8);x,y,r,b=roi.bounds(image)
    method=cv2.TM_CCOEFF_NORMED if contrast else cv2.TM_SQDIFF_NORMED
    low,high,lp,hp=cv2.minMaxLoc(cv2.matchTemplate(image[y:b,x:r],template,method))
    p=hp if contrast else lp
    result=find_template(image,template,.9,roi,contrast)
    self.assertEqual((result.x,result.y),(x+p[0],y+p[1]))
    self.assertAlmostEqual(result.confidence,high if contrast else 1-low,places=5)
 def test_full_screen_response_allocation_is_bounded(self):
  rng=np.random.default_rng(9);image=rng.integers(0,256,(900,1600),dtype=np.uint8)
  template=image[700:730,1000:1040].copy();sizes=[];original=cv2.matchTemplate
  def measured(*args):
   result=original(*args);sizes.append(result.nbytes);return result
  with patch('vision.matcher.cv2.matchTemplate',side_effect=measured):
   found=find_template(image,template,contrast_invariant=True)
  self.assertEqual((found.x,found.y),(1000,700))
  # Faster wider strips still keep each response below 3 MiB.
  self.assertLessEqual(max(sizes),3*1024*1024)
  self.assertGreater(len(sizes),1)

 def test_persistent_solver_refinement_images_have_a_fixed_limit(self):
  from fishing.solver import FishingSolver
  solver=FishingSolver();templates=[np.eye(84,dtype=np.uint8)*255]
  with patch('fishing.solver.cv2.matchTemplate',return_value=np.array([[.8]],dtype=np.float32)):
   for angle in range(24):
    target=np.full((84,84),angle,dtype=np.uint8);key=target.tobytes()
    solver._scores[key]=[.5];solver._best_variants[key]=[angle*3]
    solver._shape_scores(target,templates,refine=True,precise=True)
  self.assertLessEqual(len(solver._fine_variants),20)
  self.assertLess(sum(a.nbytes for variants in solver._fine_variants.values() for a in variants),8_000_000)
