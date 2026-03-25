import React from 'react';
import { getThumbAssetUrl } from '../utils';

const SlideThumbnailContent = ({ slide }) => {
  const slideW = slide.width || 960;
  const slideH = slide.height || 540;
  const elements = slide.elements || [];

  return (
    <>
      {elements.map((el) => {
        const toPixel = (val, base) => {
          if (typeof val === 'string' && val.endsWith('%')) return (parseFloat(val) / 100) * base;
          return val || 0;
        };
        const elX = toPixel(el.x, slideW);
        const elY = toPixel(el.y, slideH);
        const elW = toPixel(el.width, slideW) || 100;
        const elH = toPixel(el.height, slideH) || 100;

        const baseStyle = {
          position: 'absolute',
          left: elX,
          top: elY,
          width: elW,
          height: elH,
          transform: el.rotation ? `rotate(${el.rotation}deg)` : undefined,
          zIndex: el.zIndex || 0,
          overflow: 'hidden',
          opacity: el.style?.opacity > 0 ? el.style.opacity : (el.style?.opacity === 0 ? 0 : 1),
        };

        if (el.type === 'text') {
          return (
            <div key={el.id} style={{
              ...baseStyle,
              fontSize: el.style?.fontSize || 16,
              fontWeight: el.style?.fontWeight || 'normal',
              fontFamily: el.style?.fontFamily || 'inherit',
              color: el.style?.fontColor || '#000000',
              textAlign: el.style?.textAlign || 'left',
              backgroundColor: el.style?.transparentBackground ? 'transparent' : (el.style?.backgroundColor || 'transparent'),
              padding: 8,
              lineHeight: 1.2,
              borderRadius: el.style?.borderRadius || 0,
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
            }}>
              {el.content || ''}
            </div>
          );
        }

        if (el.type === 'image') {
          return (
            <div key={el.id} style={baseStyle}>
              <img
                src={getThumbAssetUrl(el.src)}
                alt=""
                style={{ width: '100%', height: '100%', objectFit: el.objectFit || 'contain', display: 'block' }}
                loading="lazy"
                draggable={false}
              />
            </div>
          );
        }

        if (el.type === 'shape') {
          return (
            <div key={el.id} style={{
              ...baseStyle,
              backgroundColor: el.style?.fill || '#7C3AED',
              border: el.style?.stroke ? `2px solid ${el.style.stroke}` : 'none',
              borderRadius: el.shapeType === 'ellipse' || el.shapeType === 'oval' ? '50%' :
                            el.shapeType === 'rounded_rectangle' ? '8px' : '0',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}>
              {el.content && (
                <span style={{ fontSize: el.style?.fontSize || 14, color: el.style?.fontColor || '#FFFFFF', textAlign: 'center', padding: 4 }}>
                  {el.content}
                </span>
              )}
            </div>
          );
        }

        if (el.type === 'video') {
          return (
            <div key={el.id} style={{ ...baseStyle, backgroundColor: '#1a1a2e', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <svg style={{ width: 48, height: 48, opacity: 0.6 }} fill="white" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
            </div>
          );
        }

        if (el.type === 'button') {
          return (
            <div key={el.id} style={{ ...baseStyle, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <div style={{
                padding: '8px 16px',
                borderRadius: el.style?.borderRadius || 8,
                fontSize: el.style?.fontSize || 16,
                color: el.buttonStyle === 'outline' ? '#9333ea' : '#fff',
                background: el.buttonStyle === 'outline' ? 'transparent' : 'linear-gradient(to right, #9333ea, #06b6d4)',
                border: el.buttonStyle === 'outline' ? '2px solid #9333ea' : 'none',
                fontWeight: 600,
              }}>
                {el.buttonText || 'Clique aqui'}
              </div>
            </div>
          );
        }

        if (el.type === 'html') {
          return (
            <div key={el.id} style={{ ...baseStyle, overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(6,182,212,0.08)', border: '1px solid rgba(6,182,212,0.25)', borderRadius: 8 }}>
              <span style={{ fontSize: 14, color: '#06b6d4', opacity: 0.6 }}>{'</>'} HTML</span>
            </div>
          );
        }

        if (el.type === 'quiz') {
          return (
            <div key={el.id} style={{ ...baseStyle, backgroundColor: 'rgba(124,58,237,0.08)', border: '1px solid rgba(124,58,237,0.25)', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <span style={{ fontSize: 14, color: '#7C3AED', opacity: 0.6 }}>Quiz</span>
            </div>
          );
        }

        return <div key={el.id} style={baseStyle} />;
      })}
    </>
  );
};

export default SlideThumbnailContent;
