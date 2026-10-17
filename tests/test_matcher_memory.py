import unittest
from unittest.mock import patch
import cv2
import numpy as np
from vision.matcher import find_template,ROI

class MatcherMemoryTests(unittest.TestCase):
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
